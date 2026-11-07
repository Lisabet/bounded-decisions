import json
from importlib.resources import files
import pytest
from decision_kit import DecisionError,DecisionRequest,ModelConfig,ProviderRegistry,execute
from decision_kit.providers import PlusVibeAdapter
from decision_kit.contract import to_record

FIXTURES=json.loads(files('decision_kit.contract_data').joinpath('fixtures.json').read_text(encoding='utf-8'))

@pytest.mark.parametrize('item',FIXTURES['cases'],ids=lambda x:x['id'])
def test_shared_operation_record(item):
    def transport(*args):
        if item['transport_error']: raise TimeoutError() if item['transport_error']=='timeout' else OSError('private')
        response=item['response'];body=response['body']
        return response['status'],response['headers'],(body if isinstance(body,str) else json.dumps(body)).encode()
    req=DecisionRequest.from_mapping(item['request']['state'],item['request']['questions'])
    cfg=ModelConfig('plusvibe',item['request']['model'])
    registry=ProviderRegistry();registry.register('plusvibe',PlusVibeAdapter(api_key='synthetic-key',endpoint='https://example.invalid/v1/decisions',transport=transport))
    try: value=execute(req,cfg,registry)
    except DecisionError as error: value=error
    actual=to_record(value,cfg,receipt_id='fixture-attempt')
    assert actual==item['expected']
    assert 'private' not in json.dumps(actual) and 'synthetic-key' not in json.dumps(actual)


def test_unknown_and_reused_are_explicit():
    err=DecisionError('timeout',uncertain=True,billed_cost=0,currency='RUB',billed_cost_provenance='fixture')
    record=to_record(err,ModelConfig('fixture','m'),receipt_id='attempt',reused=True)
    assert record['billing']['amount']==0 and record['receipt']=={'id':'attempt','reused':True}
    assert record['status']=='pending'
