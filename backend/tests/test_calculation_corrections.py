from test_cached_calculation import setup_case


def test_amount_override_and_reset_are_audited(tmp_path,monkeypatch):
    store,run,p,wid=setup_case(tmp_path,monkeypatch)
    original=store.get_matching(run)['calculation']['rows'][0]
    assert original['amount']=='7.38'
    data={'run_id':run,'movement_id':1,'amount':'8,25','reason':'HR bevestigt uitzonderingsbedrag'}
    store.apply('calculation_amount_correction',data,store.snapshot()['revision'])
    row=store.get_matching(run)['calculation']['rows'][0]
    assert row['amount']=='8.25' and row['original_amount']=='7.38' and row['amount_source']=='HR'
    assert len(row['amount_correction_history'])==1
    store.apply('calculation_amount_correction',{'run_id':run,'movement_id':1,'reset':True,'reason':'Berekening herstellen'},store.snapshot()['revision'])
    row=store.get_matching(run)['calculation']['rows'][0]
    assert row['amount']=='7.38' and row['amount_source']=='BEREKEND' and len(row['amount_correction_history'])==2


def test_invalid_amount_override_rejected(tmp_path,monkeypatch):
    import pytest
    store,run,p,wid=setup_case(tmp_path,monkeypatch)
    for amount in ('-1','1.234','abc'):
        with pytest.raises(ValueError):store.apply('calculation_amount_correction',{'run_id':run,'movement_id':1,'amount':amount,'reason':'Test'},store.snapshot()['revision'])
