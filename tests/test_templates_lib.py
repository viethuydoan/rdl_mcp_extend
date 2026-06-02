"""Tests for template-mode authoring (templates_lib)."""

import xml.etree.ElementTree as ET

from rdl_report_mcp import templates_lib, validation

NS = '{http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition}'


def _make(tmp_path, **over):
    fp = str(tmp_path / 'out.rdl')
    args = dict(
        filepath=fp, template='styled_flat_table', title='T', source_type='fabric',
        connection={'name': 'ds', 'data_source': 'srv', 'initial_catalog': 'db'},
        dataset_name='data', query='SELECT a, b FROM t',
        fields=[{'name': 'a', 'label': 'Alpha'},
                {'name': 'b', 'label': 'Beta', 'format': 'N0', 'width': '2in'}],
    )
    args.update(over)
    return fp, templates_lib.create_report_from_template(**args)


def test_list_templates_includes_styled_flat_table():
    names = [t['name'] for t in templates_lib.list_templates()['templates']]
    assert 'styled_flat_table' in names


def test_generates_one_column_per_field(tmp_path):
    fp, res = _make(tmp_path)
    assert res['success']
    root = ET.parse(fp).getroot()
    cols = root.findall(f'.//{NS}TablixColumns/{NS}TablixColumn')
    members = root.findall(f'.//{NS}TablixColumnHierarchy/{NS}TablixMembers/{NS}TablixMember')
    header_cells = root.findall(f'.//{NS}TablixRows/{NS}TablixRow')[0].findall(f'.//{NS}TablixCell')
    assert len(cols) == 2 and len(members) == 2 and len(header_cells) == 2


def test_styling_preserved_and_bindings(tmp_path):
    fp, _ = _make(tmp_path)
    txt = open(fp, encoding='utf-8').read()
    assert 'ns0:' not in txt
    assert '#305496' in txt and '<Color>White</Color>' in txt          # header band style
    assert '=Fields!a.Value' in txt and '=Fields!b.Value' in txt        # data bindings
    assert '<Value>Alpha</Value>' in txt and '<Value>Beta</Value>' in txt  # header labels
    assert '<Format>N0</Format>' in txt                                  # per-field format
    assert validation.validate_rdl(fp)['valid'] is True


def test_unknown_template_fails(tmp_path):
    _, res = _make(tmp_path, template='does_not_exist')
    assert res['success'] is False


def test_unique_textbox_names(tmp_path):
    fp, _ = _make(tmp_path)
    txt = open(fp, encoding='utf-8').read()
    import re
    names = re.findall(r'<Textbox Name="([^"]+)"', txt)
    assert len(names) == len(set(names)), f'duplicate textbox names: {names}'
