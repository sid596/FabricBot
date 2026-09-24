from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest
from pypdf import PdfReader
from google.genai import errors

from sheets import CatalogueCache
from prompt_cache import PromptCache
from quotation_pdf import QuotationReply, render_quotation_pdf
from fabric_attributes import FabricPreferences
from visual_search import rank_records, matches_filters, open_index, save_records, MODEL_NAME
import server
import whatsapp


@pytest.mark.parametrize("body", ["fabricbot", "FABRICBOT", "  FabricBot\n"])
def test_entry_command_always_returns_welcome_without_model_or_timer(monkeypatch, body):
    sent, understand, timer = Mock(), Mock(), Mock()
    monkeypatch.setattr(server, "send_message", sent)
    monkeypatch.setattr(server, "understand", understand)
    monkeypatch.setattr(server.threading, "Timer", timer)
    payload = {"entry": [{"changes": [{"value": {"messages": [
        {"from": "test", "type": "text", "text": {"body": body}}]}}]}]}
    # Re-entering after a previous request must behave the same way.
    server.process_message(payload)
    server.process_message(payload)
    assert sent.call_count == 2
    assert sent.call_args_list[0] == sent.call_args_list[1]
    assert sent.call_args.args[0] == "test"
    assert sent.call_args.args[1] == "Hi! I am Angie, how can I help you?"
    understand.assert_not_called()
    timer.assert_not_called()


def test_entry_word_inside_request_still_reaches_model(monkeypatch):
    understand = Mock(return_value={"intent": "quotation"})
    deliver = Mock()
    monkeypatch.setattr(server, "understand", understand)
    monkeypatch.setattr(server, "build_reply", Mock(return_value="quotation"))
    monkeypatch.setattr(server, "deliver_reply", deliver)
    body = "fabricbot roller blind 108 x 108"
    server.process_message({"entry": [{"changes": [{"value": {"messages": [
        {"from": "test", "type": "text", "text": {"body": body}}]}}]}]})
    understand.assert_called_once_with(body)
    deliver.assert_called_once_with("test", "quotation")

HEADERS = ["t", "Album", "Quality", "Width", "Cut Rate", "Price"]


def test_sheet_prices_refresh_without_restart_and_share_one_load():
    clock = Mock(return_value=0)
    loader = Mock(side_effect=[
        [HEADERS, ["Nuhome", "Abaca", "Nuhome Odin", "54", "625", "1450"]],
        [HEADERS, ["Nuhome", "Abaca", "Nuhome Odin", "54", "625", "1550"]],
    ])
    cache = CatalogueCache(loader, ttl=10, clock=clock)
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert all(x[1][0][-1] == "1450" for x in pool.map(lambda _: cache.get(), range(8)))
    assert loader.call_count == 1
    clock.return_value = 11
    assert cache.get()[1][0][-1] == "1550"
    assert loader.call_count == 2


def test_failed_refresh_does_not_serve_stale_price():
    clock = Mock(return_value=0)
    loader = Mock(side_effect=[[HEADERS, ["brand"]], RuntimeError("offline"), [HEADERS, ["new"]]])
    cache = CatalogueCache(loader, ttl=1, clock=clock)
    cache.get()
    clock.return_value = 2
    with pytest.raises(RuntimeError):
        cache.get()
    assert cache.get()[1][0] == ("new",)


def test_short_rows_and_blank_query(monkeypatch):
    import search
    monkeypatch.setattr(search, "get_catalogue", lambda: (HEADERS, [["Nuhome", "Cascade", "Nuhome Cascade I", "54"]]))
    assert search.search_fabric("Cascade")[0]["price"] == ""
    assert search.search_fabric(" ") == []


def test_prompt_cache_reuse_and_renewal(monkeypatch):
    import prompt_cache
    now = Mock(return_value=0)
    monkeypatch.setattr(prompt_cache.time, "monotonic", now)
    client = Mock()
    first = SimpleNamespace(name="cache/1", expire_time=datetime.now(timezone.utc) + timedelta(seconds=120))
    second = SimpleNamespace(name="cache/2", expire_time=datetime.now(timezone.utc) + timedelta(seconds=120))
    client.caches.create.side_effect = [first, second]
    cache = PromptCache(client, "model", "rules", ttl=120)
    assert cache.get() is first
    assert cache.get() is first
    now.return_value = 130
    assert cache.get() is second
    assert client.caches.create.call_count == 2


def test_server_deleted_cache_recovers_once():
    client = Mock()
    client.caches.create.return_value = SimpleNamespace(name="cache/1", expire_time=None)
    client.models.generate_content.side_effect = [errors.ClientError(404, {"error": {"message": "CachedContent not found"}}), "ok"]
    cache = PromptCache(client, "model", "rules")
    assert cache.generate("hello", dict) == "ok"
    assert client.models.generate_content.call_count == 2
    assert client.models.generate_content.call_args.kwargs["config"]["system_instruction"] == "rules"
    assert cache._cache is None


def test_cache_creation_failure_uses_full_rules():
    client = Mock()
    client.caches.create.side_effect = errors.ClientError(400, {"error": {"message": "too few tokens"}})
    client.models.generate_content.return_value = "ok"
    assert PromptCache(client, "model", "rules").generate("hello", dict) == "ok"
    assert client.models.generate_content.call_args.kwargs["config"]["system_instruction"] == "rules"


def quote_request(count=1):
    return {"intent": "quotation", "line_items": [
        {"room": f"Bedroom {i+1}", "curtain_type": "main", "height": 84, "width": 96,
         "fabric_price": 590, "order_type": "full"} for i in range(count)]}


def test_complete_quote_pdf_preserves_amounts_and_unicode():
    reply = server.build_reply(quote_request(), server.quote_config)
    assert isinstance(reply, QuotationReply)
    pdf = render_quotation_pdf(reply, reference="TEST-001")
    text = "\n".join(page.extract_text() for page in PdfReader(BytesIO(pdf)).pages)
    assert "₹" in text
    for line in reply.splitlines():
        if "₹" in line:
            assert line.split("₹")[-1].strip() in text
    assert "TEST-001" in text
    assert "Bedroom 1 / main" in text


def test_long_quote_paginates_and_preserves_grand_total():
    reply = server.build_reply(quote_request(12), server.quote_config)
    pages = PdfReader(BytesIO(render_quotation_pdf(reply))).pages
    assert len(pages) > 1
    text = "\n".join(page.extract_text() for page in pages)
    assert "Bedroom 12" in text and "GRAND TOTAL" in text
    assert reply.split("GRAND TOTAL: ")[1].split("*")[0] in text


def test_missing_dimensions_remains_text(monkeypatch):
    reply = server.build_reply({"intent": "quotation", "line_items": [{"room": "Bedroom"}]}, server.quote_config)
    assert not isinstance(reply, QuotationReply)
    send, document = Mock(), Mock()
    monkeypatch.setattr(server, "send_message", send)
    monkeypatch.setattr(server, "send_document", document)
    server.deliver_reply("test", reply)
    send.assert_called_once()
    document.assert_not_called()


def test_pdf_delivery_uses_upload_and_document_type(monkeypatch):
    post = Mock()
    post.return_value.json.side_effect = [{"id": "media-1"}, {"messages": [{"id": "msg-1"}]}]
    monkeypatch.setattr(whatsapp.requests, "post", post)
    whatsapp.send_document("test", b"%PDF-example")
    upload, send = post.call_args_list
    assert upload.kwargs["files"]["file"][2] == "application/pdf"
    assert send.kwargs["json"]["type"] == "document"
    assert send.kwargs["json"]["document"]["id"] == "media-1"


def test_failed_media_upload_does_not_send_document(monkeypatch):
    post = Mock()
    post.return_value.raise_for_status.side_effect = RuntimeError("upload failed")
    monkeypatch.setattr(whatsapp.requests, "post", post)
    with pytest.raises(RuntimeError):
        whatsapp.send_document("test", b"pdf")
    assert post.call_count == 1


def test_filters_distinguish_texture_composition_and_dual_use():
    record = {"uses": ["sheer"], "composition": "100% Polyester"}
    assert matches_filters(record, FabricPreferences(textures=["linen look"]))
    assert not matches_filters(record, FabricPreferences(materials=["linen"]))
    assert not matches_filters(record, FabricPreferences(fabric_type="main"))
    assert not matches_filters(record, FabricPreferences(fabric_type="both"))
    record["uses"].append("main")
    assert matches_filters(record, FabricPreferences(fabric_type="both"))
    assert not matches_filters(record, FabricPreferences(materials=["natural"]))


def test_ranking_caps_at_five_uses_current_prices_and_excludes_unlisted(tmp_path):
    photo = tmp_path / "fabric.jpg"
    photo.write_bytes(b"fixture")
    records = [{"id": str(i), "brand": "Nuhome", "album": "Abaca", "quality": "Nuhome Odin",
                "uses": ["main"], "image_path": str(photo)} for i in range(8)]
    records.append({**records[0], "id": "unlisted", "quality": "Other"})
    prices = [{**records[0], "price": "1550", "width": "54"}]
    vectors = np.array([[i / 10, 0] for i in range(8)] + [[1, 0]])
    matches = rank_records(records, vectors, np.array([1, 0]), FabricPreferences(), prices, 5)
    assert [r["id"] for r in matches] == ["7", "6", "5", "4", "3"]
    assert all(r["price"] == "1550" for r in matches)
    assert not rank_records(records, vectors, np.array([1, 0]), FabricPreferences(fabric_type="sheer"), prices, 5)


def test_index_updates_are_visible_without_restart(tmp_path):
    path = tmp_path / "fabrics.db"
    first, second = open_index(path), open_index(path)
    save_records(first, [{"id": "one"}], [[1., 0.]])
    assert second.execute("SELECT count(*) FROM fabrics").fetchone()[0] == 1
    save_records(first, [{"id": "two"}], [[0., 1.]])
    assert second.execute("SELECT count(*) FROM fabrics").fetchone()[0] == 2
    first.close()
    second.close()


def test_photo_search_routes_and_cleans_temp_file(tmp_path, monkeypatch):
    photo = tmp_path / "incoming.jpg"
    photo.write_bytes(b"fixture")
    monkeypatch.setattr(server, "download_image", lambda _: str(photo))
    monkeypatch.setattr(server, "extract_visual_content", lambda *a: {"content_type": "fabric_photo", "search_preferences": {"colours": ["sage green"]}})
    search = Mock()
    monkeypatch.setattr(server, "deliver_search", search)
    server.process_message({"entry": [{"changes": [{"value": {"messages": [
        {"from": "test", "type": "image", "image": {"id": "photo1"}}]}}]}]})
    search.assert_called_once_with("test", {"colours": ["sage green"]}, str(photo))
    assert not photo.exists()


def test_exactly_five_images_sent(monkeypatch):
    matches = [{"image_path": f"{i}.jpg"} for i in range(5)]
    monkeypatch.setattr(server, "find_similar", lambda *a: matches)
    monkeypatch.setattr(server, "match_caption", lambda m, n: str(n))
    monkeypatch.setattr(server, "send_message", Mock())
    images = Mock()
    monkeypatch.setattr(server, "send_image", images)
    server.deliver_search("test", {})
    assert images.call_count == 5


def test_search_reads_new_index_commits_and_new_prices(tmp_path, monkeypatch):
    import visual_search
    photo = tmp_path / 'photo.jpg'
    photo.write_bytes(b'fixture')
    db_path = tmp_path / 'catalogue.db'
    db = open_index(db_path)
    record = {'id':'one','brand':'Nuhome','album':'Abaca','quality':'Nuhome Odin','image_path':str(photo),'uses':['main']}
    save_records(db, [record], [[1., 0.]])
    monkeypatch.setattr(visual_search, 'encode', lambda _: np.array([[1., 0.]]))
    price = {**record, 'price':'1450','width':'54'}
    monkeypatch.setattr(visual_search, 'catalogue_records', lambda: [price])
    assert visual_search.find_similar({'description':'green'}, db_path=db_path)[0]['price']=='1450'
    price['price']='1550'
    save_records(db, [{**record,'id':'two'}], [[.8,.6]])
    result=visual_search.find_similar({'description':'green'}, db_path=db_path)
    assert len(result)==2 and all(r['price']=='1550' for r in result)
    db.close()


def test_quotation_note_preserves_review_workflow(tmp_path, monkeypatch):
    photo=tmp_path/'note.jpg'; photo.write_bytes(b'fixture')
    monkeypatch.setattr(server,'download_image',lambda _:str(photo))
    monkeypatch.setattr(server,'extract_visual_content',lambda *a:{'content_type':'quotation_table','line_items':[{'room':'Living room','height':84,'width':96,'fabric':'Luna'}]})
    sent=Mock(); documents=Mock()
    monkeypatch.setattr(server,'send_message',sent)
    monkeypatch.setattr(server,'send_document',documents)
    server.process_message({'entry':[{'changes':[{'value':{'messages':[{'from':'test','type':'image','image':{'id':'note'}}]}}]}]})
    assert '84x96' in sent.call_args.args[1]
    documents.assert_not_called()
    assert not photo.exists()


def test_text_search_routes_to_images_without_price_lookup(monkeypatch):
    monkeypatch.setattr(server,'understand',lambda _: {'intent':'fabric_search','search_preferences':{'colours':['teal']}})
    lookup=Mock(); search=Mock()
    monkeypatch.setattr(server,'build_reply',lookup)
    monkeypatch.setattr(server,'deliver_search',search)
    server.process_message({'entry':[{'changes':[{'value':{'messages':[{'from':'test','type':'text','text':{'body':'show teal fabrics'}}]}}]}]})
    search.assert_called_once_with('test', {'colours':['teal']})
    lookup.assert_not_called()


def test_mixed_curtain_blind_pdf_retains_all_totals():
    request=quote_request()
    request['line_items'].append({'room':'Study','blind_type':'roller','height':60,'width':48})
    reply=server.build_reply(request,server.quote_config)
    text='\n'.join(p.extract_text() for p in PdfReader(BytesIO(render_quotation_pdf(reply))).pages)
    assert 'Roller Blind' in text and 'Bedroom 1' in text
    for label in ('Total Fabric Cost','Total Blind Area Cost','Total GST','GRAND TOTAL'):
        value=next(line.split(':',1)[1].strip().strip('*') for line in reply.splitlines() if label in line)
        assert value in text


def test_cache_creation_failure_has_a_retry_backoff(monkeypatch):
    import prompt_cache
    clock=Mock(return_value=0)
    monkeypatch.setattr(prompt_cache.time,'monotonic',clock)
    client=Mock()
    client.caches.create.side_effect=errors.ClientError(429,{'error':{'message':'quota'}})
    cache=PromptCache(client,'model','rules')
    cache.generate('one',dict)
    cache.generate('two',dict)
    assert client.caches.create.call_count==1
    clock.return_value=61
    cache.generate('three',dict)
    assert client.caches.create.call_count==2


def test_same_fabric_sku_across_albums_is_returned_only_once(tmp_path):
    photo=tmp_path/'photo.jpg';photo.write_bytes(b'fixture')
    rows=[{'id':str(i),'brand':'Nuhome','album':f'Album {i}',
           'quality':'Nuhome Zany','sku':'422' if i<2 else str(i),
           'uses':['main'],'image_path':str(photo)} for i in range(7)]
    prices=[{**r,'price':'1890','width':'54'} for r in rows]
    vectors=np.array([[.8,0],[1.,0],[.7,0],[.6,0],[.5,0],[.4,0],[.3,0]])
    results=rank_records(rows,vectors,np.array([1.,0]),FabricPreferences(),prices,5)
    assert len(results)==5
    assert len({(r['quality'],r['sku']) for r in results})==5
    assert results[0]['id']=='1'
