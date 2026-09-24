from copy import deepcopy
from unittest.mock import Mock

import pytest

import server
from quote_conversation import DraftStore, QuoteConversation, validate_draft
from quotation_pdf import QuotationReply


def curtain(**changes):
    line = dict(room='Living', window='W1', product='curtain', height=84, width=96,
                unit='inches', measurement_basis='window_opening', curtain_type='main',
                order_type='full', fabric='Odin', brand='Nuhome', album='Abaca', sku='220',
                track='MTrack Premium', curtain_style='Pleated', lining='none')
    line.update(changes)
    return line


def catalogue():
    return [dict(brand='Nuhome', album='Abaca', quality='Nuhome Odin', price='1450', width='54')]


def flow(tmp_path, drafts):
    store = DraftStore(tmp_path / 'sessions.db')
    send, deliver = Mock(), Mock()
    extract = Mock(side_effect=drafts)
    conversation = QuoteConversation(store, server.quote_config, catalogue, server.build_reply,
                                     send, deliver, extract)
    return conversation, store, send, deliver, extract


def test_photo_followups_review_and_explicit_confirmation(tmp_path):
    incomplete = {'line_items': [curtain(height=None, width=None, unit=None)]}
    complete = {'line_items': [curtain()]}
    c, store, send, deliver, extract = flow(tmp_path, [incomplete, complete])
    store.put('alice', {'references': ['Photo label: Nuhome Abaca Odin 220']})
    c.handle('alice', 'Quote this fabric for living window W1')
    assert 'height' in send.call_args.args[1]
    deliver.assert_not_called()
    c.handle('alice', 'Height 84 width 96 inches, window opening')
    assert 'confirm quotation' in send.call_args.args[1]
    assert '220' in store.get('alice')['preview']
    history = extract.call_args.args[0]
    assert history[0]['text'] == 'Photo label: Nuhome Abaca Odin 220'
    assert any('Quote this fabric' in h['text'] for h in history)
    deliver.assert_not_called()
    c.handle('bob', 'confirm quotation')
    deliver.assert_not_called()
    preview = store.get('alice')['preview']
    # Simulate a process restart; both extraction and lookup must be unnecessary.
    restarted = QuoteConversation(DraftStore(store.path), server.quote_config, Mock(side_effect=AssertionError),
                                  Mock(side_effect=AssertionError), send, deliver)
    restarted.handle('alice', 'CONFIRM QUOTATION')
    deliver.assert_called_once_with('alice', QuotationReply(preview))
    assert not store.get('alice')
    restarted.handle('alice', 'confirm quotation')
    assert deliver.call_count == 1


def test_correction_invalidates_confirmation_even_if_extraction_fails(tmp_path):
    c, store, send, deliver, extract = flow(tmp_path, [{'line_items': [curtain()]}, RuntimeError('offline')])
    c.handle('alice', 'complete request')
    assert store.get('alice')['preview']
    with pytest.raises(RuntimeError):
        c.handle('alice', 'Actually change width to 120 inches')
    c.handle('alice', 'confirm quotation')
    deliver.assert_not_called()
    assert store.get('alice')['preview'] is None


def test_correction_requires_new_review(tmp_path):
    c, store, send, deliver, _ = flow(tmp_path, [{'line_items': [curtain()]}, {'line_items': [curtain(width=120)]}])
    c.handle('alice', 'first')
    previous = store.get('alice')['preview']
    c.handle('alice', 'make width 120 inches')
    assert 'width 120' in store.get('alice')['preview']
    assert previous != store.get('alice')['preview']
    deliver.assert_not_called()


def test_unfinished_confirmation_cancel_and_expiry(tmp_path):
    c, store, send, deliver, _ = flow(tmp_path, [{'line_items': [curtain(unit=None)]}])
    c.handle('alice', 'quote')
    c.handle('alice', 'confirm quotation')
    deliver.assert_not_called()
    c.handle('alice', 'cancel quotation')
    assert not store.get('alice')
    clock = Mock(return_value=0)
    expiring = DraftStore(tmp_path / 'expiry.db', ttl=10, clock=clock)
    expiring.put('alice', {'active': True, 'preview': 'old'})
    clock.return_value = 11
    assert not expiring.get('alice')


@pytest.mark.parametrize('change,question', [
    ({'height': -1}, 'positive height'),
    ({'unit': None}, 'inches, feet'),
    ({'measurement_basis': None}, 'window/opening'),
    ({'fabric': None}, 'exact fabric'),
    ({'sku': None}, 'colour/design'),
    ({'curtain_style': None}, 'stitching style'),
    ({'track': None}, 'Which track'),
    ({'lining': 'blackout'}, 'lining needs'),
    ({'order_type': None}, 'new tracks'),
])
def test_ambiguities_block_preview(change, question):
    _, questions, _ = validate_draft({'line_items': [curtain(**change)]}, catalogue(), server.quote_config)
    assert any(question in q for q in questions)


def test_ambiguous_catalogue_is_not_first_match_and_sheet_width_is_used():
    rows = catalogue() + [{**catalogue()[0], 'album': 'Other', 'price': '999'}]
    _, questions, _ = validate_draft({'line_items': [curtain(album=None)]}, rows, server.quote_config)
    assert any('Other' in q for q in questions)
    result, questions, _ = validate_draft({'line_items': [curtain()]}, rows, server.quote_config)
    assert not questions
    assert result['line_items'][0]['_resolved_fabric']['width'] == '54'
    assert result['line_items'][0]['fabric_price'] == '1450'
    quote = server.build_reply(result, server.quote_config)
    assert isinstance(quote, QuotationReply)
    assert '220' in quote


def test_mixed_windows_unit_conversion_and_unknown_requests():
    roller = dict(room='Study', window='W2', product='roller', height=7, width=6, unit='feet',
                  measurement_basis='window_opening', sku='White R1', with_pelmet=False)
    draft = {'line_items': [curtain(), roller], 'open_questions': ['Do you want a separate quote for automation?']}
    _, questions, _ = validate_draft(draft, catalogue(), server.quote_config)
    assert questions == draft['open_questions']
    draft['open_questions'] = []
    result, questions, _ = validate_draft(draft, catalogue(), server.quote_config)
    assert not questions
    assert result['line_items'][1]['height'] == 84
    assert result['line_items'][1]['width'] == 72
    assert isinstance(server.build_reply(result, server.quote_config), QuotationReply)
    draft['line_items'][1]['with_pelmet'] = None
    assert any('pelmet' in q for q in validate_draft(draft, catalogue(), server.quote_config)[1])


def test_review_delivery_failure_cannot_authorize_pdf(tmp_path):
    c, store, send, deliver, _ = flow(tmp_path, [{'line_items': [curtain()]}])
    send.side_effect = RuntimeError('WhatsApp unavailable')
    with pytest.raises(RuntimeError):
        c.handle('alice', 'quote')
    assert not store.get('alice').get('preview')
    send.side_effect = None
    c.handle('alice', 'confirm quotation')
    deliver.assert_not_called()


def test_failed_pdf_delivery_retains_review_for_retry(tmp_path):
    c, store, _, deliver, _ = flow(tmp_path, [{'line_items': [curtain()]}])
    c.handle('alice', 'quote')
    deliver.side_effect = RuntimeError('upload unavailable')
    with pytest.raises(RuntimeError):
        c.handle('alice', 'confirm quotation')
    assert store.get('alice')['preview']


def payload(body=None, caption=None):
    message = {'from': 'alice', 'type': 'text', 'text': {'body': body}} if body is not None else {
        'from': 'alice', 'type': 'image', 'image': {'id': 'photo', 'caption': caption or ''}}
    return {'entry': [{'changes': [{'value': {'messages': [message]}}]}]}


def test_photo_caption_and_next_message_use_same_draft(tmp_path, monkeypatch):
    photo = tmp_path / 'photo.jpg'
    photo.write_bytes(b'fixture')
    monkeypatch.setattr(server, 'download_image', lambda _: str(photo))
    monkeypatch.setattr(server, 'extract_visual_content', lambda *args: {
        'content_type': 'product_code', 'code': 'Odin', 'label_text': 'Nuhome Abaca Odin 220', 'quotation_requested': True})
    c, store, send, deliver, extract = flow(tmp_path, [
        {'line_items': [curtain(unit=None)]}, {'line_items': [curtain()]}])
    monkeypatch.setattr(server, 'draft_store', store)
    monkeypatch.setattr(server, 'quotation_conversation', lambda: c)
    understand = Mock()
    monkeypatch.setattr(server, 'understand', understand)
    server.process_message(payload(caption='Quote for living W1 height 84 width 96'))
    assert not photo.exists()
    assert 'Odin 220' in extract.call_args.args[0][0]['text']
    assert 'height 84 width 96' in extract.call_args.args[0][0]['text']
    server.process_message(payload(body='inches'))
    understand.assert_not_called()
    deliver.assert_not_called()
    server.process_message(payload(body='confirm quotation'))
    deliver.assert_called_once()


def test_plain_tag_remembered_for_later_quote(tmp_path, monkeypatch):
    photo = tmp_path / 'photo.jpg'; photo.write_bytes(b'fixture')
    monkeypatch.setattr(server, 'download_image', lambda _: str(photo))
    monkeypatch.setattr(server, 'extract_visual_content', lambda *a: {'content_type':'product_code', 'code':'Odin', 'label_text':'Odin 220'})
    monkeypatch.setattr(server, 'understand', lambda _: {'intent':'price_lookup', 'fabric':'Odin'})
    monkeypatch.setattr(server, 'build_reply', lambda *a: 'Price')
    monkeypatch.setattr(server, 'send_message', Mock())
    server.process_message(payload())
    assert 'Odin 220' in server.draft_store.get('alice')['references'][0]


def test_new_quotation_discards_previous_windows_and_photos(tmp_path):
    c, store, _, deliver, extract = flow(tmp_path, [{'line_items': []}])
    store.put('alice', {'active': True, 'preview': 'old', 'references': ['old photo'],
                        'history': [{'role': 'user', 'text': 'old dimensions'}]})
    c.handle('alice', 'new quotation')
    assert extract.call_args.args[0][0]['text'] == 'new quotation'
    assert 'old dimensions' not in str(extract.call_args.args[0])
    assert not store.get('alice').get('preview')
    deliver.assert_not_called()


def test_two_workers_serialize_updates_for_same_sender(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    a, b = DraftStore(tmp_path / 'shared.db'), DraftStore(tmp_path / 'shared.db')
    def increment(store):
        with store.serialized('alice'):
            state = store.get('alice')
            state['count'] = state.get('count', 0) + 1
            store.put('alice', state)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(increment, [a, b] * 10))
    assert a.get('alice')['count'] == 20


def test_long_review_is_split_and_all_windows_remain_in_pdf_payload(tmp_path):
    lines = [curtain(window=f'Window {i}') for i in range(12)]
    c, store, send, deliver, _ = flow(tmp_path, [{'line_items': lines}])
    c.handle('alice', '12 windows')
    assert send.call_count > 1
    assert all(len(call.args[1]) <= 3500 for call in send.call_args_list)
    assert 'Window 11' in store.get('alice')['preview']
    deliver.assert_not_called()


def test_track_only_does_not_require_curtain_fields():
    line = dict(room='Living', window='W1', product='curtain', order_type='track_only',
                width=8, unit='feet', measurement_basis='track_length', track='MTrack Premium')
    result, questions, _ = validate_draft({'line_items': [line]}, [], server.quote_config)
    assert not questions
    assert isinstance(server.build_reply(result, server.quote_config), QuotationReply)


def test_compound_album_quality_is_resolved_without_guessing():
    result, questions, _ = validate_draft({'line_items': [curtain(fabric='Abaca Odin', album=None)]}, catalogue(), server.quote_config)
    assert not questions
    assert result['line_items'][0]['_resolved_fabric']['quality'] == 'Nuhome Odin'
