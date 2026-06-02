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


# --- matrix template ---

def _make_matrix(tmp_path, **over):
    fp = str(tmp_path / 'matrix.rdl')
    args = dict(
        filepath=fp, template='simple_matrix', title='M', source_type='fabric',
        connection={'name': 'ds', 'data_source': 'srv', 'initial_catalog': 'db'},
        dataset_name='data', query='SELECT r, c, v FROM t',
        fields=[{'name': 'r'}, {'name': 'c', 'type_name': 'System.DateTime'},
                {'name': 'v', 'type_name': 'System.Decimal'}],
        bindings={'row_group': 'r', 'column_group': 'c', 'value': 'v',
                  'aggregate': 'Sum', 'value_format': 'N0'},
    )
    args.update(over)
    return fp, templates_lib.create_report_from_template(**args)


def test_simple_matrix_in_library():
    names = [t['name'] for t in templates_lib.list_templates()['templates']]
    assert 'simple_matrix' in names


def test_matrix_rebinds_groups_and_value(tmp_path):
    fp, res = _make_matrix(tmp_path)
    assert res['success'], res['message']
    txt = open(fp, encoding='utf-8').read()
    assert 'ns0:' not in txt and '<TablixCorner>' in txt
    root = ET.parse(fp).getroot()
    ges = sorted(g.text for g in root.findall(f'.//{NS}GroupExpression'))
    assert ges == ['=Fields!c.Value', '=Fields!r.Value']
    value = root.find(f".//{NS}TablixBody//{NS}Value").text
    assert value == '=Sum(Fields!v.Value)'
    assert '<Format>N0</Format>' in txt
    assert validation.validate_rdl(fp)['valid'] is True


def test_matrix_custom_aggregate(tmp_path):
    fp, _ = _make_matrix(tmp_path, bindings={'row_group': 'r', 'column_group': 'c',
                                             'value': 'v', 'aggregate': 'Avg'})
    assert '=Avg(Fields!v.Value)' in open(fp, encoding='utf-8').read()


def test_matrix_missing_bindings_fails(tmp_path):
    fp = str(tmp_path / 'm.rdl')
    res = templates_lib.create_report_from_template(
        filepath=fp, template='simple_matrix', title='M', source_type='fabric',
        connection={'name': 'd', 'data_source': 's', 'initial_catalog': 'd'},
        dataset_name='data', query='SELECT 1', fields=[{'name': 'r'}], bindings=None)
    assert res['success'] is False and 'bindings' in res['message'].lower()


# --- grouped (nested row groups) matrix template ---

def _make_grouped(tmp_path, **over):
    fp = str(tmp_path / 'grouped.rdl')
    args = dict(
        filepath=fp, template='matrix_grouped', title='G', source_type='fabric',
        connection={'name': 'ds', 'data_source': 'srv', 'initial_catalog': 'db'},
        dataset_name='data', query='SELECT r1, r2, c, v FROM t',
        fields=[{'name': 'r1'}, {'name': 'r2'}, {'name': 'c'},
                {'name': 'v', 'type_name': 'System.Decimal'}],
        bindings={'row_groups': ['r1', 'r2'], 'column_group': 'c', 'value': 'v',
                  'aggregate': 'Sum', 'row_group_labels': ['Region', 'Facility']},
    )
    args.update(over)
    return fp, templates_lib.create_report_from_template(**args)


def test_grouped_nested_row_groups_independent_sorts(tmp_path):
    fp, res = _make_grouped(tmp_path)
    assert res['success'], res['message']
    root = ET.parse(fp).getroot()
    rh = root.find(f'.//{NS}TablixRowHierarchy')
    # Each row-group member must carry its OWN group + sort expression (no cross-contamination)
    pairs = {}
    for m in rh.iter(f'{NS}TablixMember'):
        g = m.find(f'{NS}Group')
        if g is None:
            continue
        ge = m.find(f'{NS}Group/{NS}GroupExpressions/{NS}GroupExpression').text
        sv = m.find(f'{NS}SortExpressions/{NS}SortExpression/{NS}Value').text
        pairs[g.get('Name')] = (ge, sv)
    assert pairs['RowGroupOuter'] == ('=Fields!r1.Value', '=Fields!r1.Value')
    assert pairs['RowGroupInner'] == ('=Fields!r2.Value', '=Fields!r2.Value')
    assert validation.validate_rdl(fp)['valid'] is True


def test_grouped_corner_labels_and_value(tmp_path):
    fp, _ = _make_grouped(tmp_path)
    corner_vals = [t.find(f'.//{NS}Value').text
                   for t in ET.parse(fp).getroot().findall(f'.//{NS}TablixCorner//{NS}Textbox')]
    assert corner_vals == ['Region', 'Facility']
    assert '=Sum(Fields!v.Value)' in open(fp, encoding='utf-8').read()


def test_grouped_wrong_row_group_count_fails(tmp_path):
    _, res = _make_grouped(tmp_path, bindings={'row_groups': ['r1'], 'column_group': 'c', 'value': 'v'})
    assert res['success'] is False and 'row group' in res['message'].lower()


# --- composite (matrix + table) template ---

def _make_composite(tmp_path, **over):
    fp = str(tmp_path / 'composite.rdl')
    args = dict(
        filepath=fp, template='matrix_and_table', title='C', source_type='fabric',
        connection={'name': 'ds', 'data_source': 'srv', 'initial_catalog': 'db'},
        datasets=[
            {'name': 'MatrixData', 'query': 'SELECT r,c,v FROM t',
             'fields': [{'name': 'r'}, {'name': 'c'}, {'name': 'v', 'type_name': 'System.Decimal'}]},
            {'name': 'TableData', 'query': 'SELECT a,b FROM t',
             'fields': [{'name': 'a'}, {'name': 'b', 'type_name': 'System.Decimal'}]},
        ],
        regions={
            'matrix': {'bindings': {'row_group': 'r', 'column_group': 'c', 'value': 'v'}},
            'table': {'columns': [{'name': 'a', 'label': 'A'}, {'name': 'b', 'label': 'B', 'format': 'N0'}]},
        },
    )
    args.update(over)
    return fp, templates_lib.create_composite_report_from_template(**args)


def test_composite_two_datasets_two_regions(tmp_path):
    fp, res = _make_composite(tmp_path)
    assert res['success'], res['message']
    root = ET.parse(fp).getroot()
    assert [d.get('Name') for d in root.findall(f'.//{NS}DataSet')] == ['MatrixData', 'TableData']
    mt = root.find(f".//{NS}Tablix[@Name='MatrixTablix']")
    tt = root.find(f".//{NS}Tablix[@Name='TableTablix']")
    assert mt.find(f'{NS}DataSetName').text == 'MatrixData'
    assert tt.find(f'{NS}DataSetName').text == 'TableData'
    assert sorted(g.text for g in mt.findall(f'.//{NS}GroupExpression')) == ['=Fields!c.Value', '=Fields!r.Value']
    assert len(tt.findall(f'.//{NS}TablixColumns/{NS}TablixColumn')) == 2
    txt = open(fp, encoding='utf-8').read()
    assert 'ns0:' not in txt and '=Fields!a.Value' in txt
    assert validation.validate_rdl(fp)['valid'] is True


def test_composite_missing_dataset_fails(tmp_path):
    _, res = _make_composite(tmp_path, datasets=[
        {'name': 'MatrixData', 'query': 'SELECT r,c,v', 'fields': [{'name': 'r'}, {'name': 'c'}, {'name': 'v'}]}])
    assert res['success'] is False and 'tabledata' in res['message'].lower()


def test_composite_rejects_single_region_template(tmp_path):
    _, res = _make_composite(tmp_path, template='simple_matrix')
    assert res['success'] is False and 'composite' in res['message'].lower()
