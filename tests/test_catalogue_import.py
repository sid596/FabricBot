from bs4 import BeautifulSoup
import pytest
from catalogue_import import parse_product, parse_patterns, checked_url


def test_variants_are_read_from_complete_colour_list_and_keep_supplier_metadata():
    html = '''<ul class="sku_detail_info_list">
    <li class="sku_detail_info_item"><span class="sku_detail_info_label">End Use</span><span class="sku_detail_info">Curtains</span></li>
    <li class="sku_detail_info_item"><span class="sku_detail_info_label">Category</span><span class="sku_detail_info">Sheers, Textures</span></li>
    <li class="sku_detail_info_item"><span class="sku_detail_info_label">Composition</span><span class="sku_detail_info">100% Polyester</span></li></ul>
    <div class="sku_colors_list"><a href="/album/fabric/1/101"><img src="/storage/a.jpg"></a>
    <a href="/album/fabric/1/102"><img src="/storage/b.jpg"></a></div>'''
    rows = parse_product(BeautifulSoup(html, 'html.parser'), {"brand": "Nuhome", "album": "Album", "quality": "Nuhome Fabric"})
    assert len(rows) == 2
    assert {r["sku"] for r in rows} == {"101", "102"}
    assert all(r["uses"] == ["sheer"] for r in rows)
    assert all(r["composition"] == "100% Polyester" for r in rows)


def test_import_refuses_links_outside_the_source():
    with pytest.raises(ValueError):
        checked_url('https://example.com/photo.jpg')
    with pytest.raises(ValueError):
        checked_url('file:///tmp/photo.jpg')


def test_no_guessed_variant_links_when_site_changes():
    with pytest.raises(ValueError, match="No colour variants"):
        parse_product(BeautifulSoup('<p>New page</p>', 'html.parser'), {})


def test_discovery_follows_sku_pagination_and_keeps_coordinating_fabrics():
    from catalogue_import import discover_patterns
    root='https://www.nuhome.in/collection-detail/example'
    pages={root:'''<div id="tab-patterns"><div class="product_list_wrap"><a href="/example/plain/1/101"><div class="product_title">Plain</div></a></div></div>
    <div id="tab-skus"><a rel="next" href="/collection-detail/example?product_page=2">Next</a></div>''',
    root+'?product_page=2':'''<div id="tab-skus"><div class="product_list_wrap"><a href="/example/sheer/2/201"><div class="product_title">Sheer</div></a></div></div>'''}
    class Web:
        def page(self,url):
            return BeautifulSoup(pages[url],'html.parser')
    assert discover_patterns(Web(),root)==[
        ('Plain','https://www.nuhome.in/example/plain/1/101'),
        ('Sheer','https://www.nuhome.in/example/sheer/2/201')]


def test_explicit_refresh_reloads_existing_photo(tmp_path, monkeypatch):
    from io import BytesIO
    from PIL import Image
    from unittest.mock import Mock
    import catalogue_import
    old = tmp_path/'fabric.jpg'
    Image.new('RGB',(10,10),'red').save(old)
    buffer=BytesIO()
    Image.new('RGB',(10,10),'green').save(buffer,format='JPEG')
    response=Mock(content=buffer.getvalue())
    get=Mock(return_value=response)
    monkeypatch.setattr(catalogue_import.requests,'get',get)
    record={'id':'fabric','image_url':'https://www.nuhome.in/photo.jpg'}
    catalogue_import.download_photo(record,tmp_path)
    get.assert_not_called()
    catalogue_import.download_photo(record,tmp_path,refresh=True)
    get.assert_called_once()
    with Image.open(old) as photo:
        r,g,b=photo.getpixel((0,0))
        assert g>r
