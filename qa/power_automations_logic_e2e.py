"""Exercise saved workflows through local HTTP APIs and the real background worker.

Run from backend: venv/Scripts/python.exe ../qa/power_automations_logic_e2e.py
Creates reusable manual-only examples in Power Apps Automations / Development.
"""
import json
import argparse
import sys
import time
import uuid
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app.core.security import create_access_token
from app.apps.power_apps.node_registry import NODES
from app.apps.power_apps.graph import VisualWorkflowDefinition

API = 'http://127.0.0.1:1534/api/v1'
session = requests.Session()
session.headers.update(Authorization='Bearer ' + create_access_token(26), **{'X-Suite-Branch': '1'})


def request(method, path, **kwargs):
    response = session.request(method, API + path, timeout=30, **kwargs)
    if not response.ok:
        details = response.json().get('detail', response.text)
        if isinstance(details, list):
            details = [{key: value for key, value in error.items() if key in {'loc', 'msg'}} for error in details[-6:]]
        raise RuntimeError(f'{method} {path}: {response.status_code} {details}')
    return response.json()


def node(id, kind, **config):
    return dict(id=id, type=kind, label=NODES[kind]['name'], position={'x': 100 + len(id) * 60, 'y': 150},
                config={**{f['key']: f['default'] for f in NODES[kind]['fields'] if 'default' in f}, **config})


def edge(source, target, port='out'):
    return dict(id=f'{source}_{port}_{target}', source=source, target=target, source_port=port, target_port='in')


def graph(nodes, edges):
    nodes = [node('start', 'manual_trigger'), *nodes]
    depths = {'start': 0}
    for _ in nodes:
        for link in edges:
            if link['source'] in depths:
                depths[link['target']] = max(depths.get(link['target'], 0), depths[link['source']] + 1)
    rows = {}
    for item in nodes:
        depth = depths[item['id']]
        row = rows.get(depth, 0)
        item['position'] = {'x': 80 + depth * 300, 'y': 100 + row * 220}
        rows[depth] = row + 1
    return {'schema_version': 2, 'nodes': nodes, 'edges': edges, 'tags': ['E2E examples']}


def condition_graph(config, kind='if_else'):
    return graph([node('check', kind, **config), node('yes', 'log_event', message='IF path'), node('no', 'log_event', message='ELSE path')],
                 [edge('start', 'check'), edge('check', 'yes', 'true'), edge('check', 'no', 'false')])


def loop_graph(kind='for_each', **config):
    return graph([node('repeat', kind, **config), node('body', 'log_event', message='Item {{steps.repeat.output.value}}'), node('done', 'log_event', message='Loop finished')],
                 [edge('start', 'repeat'), edge('repeat', 'body', 'body'), edge('repeat', 'done', 'done')])


def scenarios():
    simple = condition_graph({'left': '{{trigger.input.amount}}', 'operator': 'greater_or_equal', 'right': 1000})
    compound = condition_graph({'condition': {'join': 'and', 'rules': [
        {'left': '{{trigger.input.active}}', 'operator': 'boolean_equals', 'right': True},
        {'join': 'or', 'rules': [
            {'left': '{{trigger.input.region}}', 'operator': 'equals', 'right': 'India'},
            {'left': '{{trigger.input.priority}}', 'operator': 'equals', 'right': 'High'},
        ]},
    ]}})
    nested = graph([
        node('outer', 'for_each', items=['A', 'B'], max_iterations=2, mode='bounded_parallel', concurrency=2),
        node('inner', 'loop', max_iterations=2), node('body', 'log_event', message='Nested {{steps.inner.output.value}}'),
        node('inner_done', 'log_event', message='Inner complete'), node('done', 'log_event', message='All complete'),
    ], [edge('start', 'outer'), edge('outer', 'inner', 'body'), edge('inner', 'body', 'body'), edge('inner', 'inner_done', 'done'), edge('outer', 'done', 'done')])
    switch = graph([node('route', 'switch', value='{{trigger.input.priority}}'), node('high', 'log_event', message='High route'),
                    node('low', 'log_event', message='Low route'), node('fallback', 'log_event', message='Default route')],
                   [edge('start', 'route'), edge('route', 'high', 'route_1'), edge('route', 'low', 'route_2'), edge('route', 'fallback', 'default')])
    early_exit = graph([
        node('repeat', 'loop', max_iterations=5, exit_condition={'join': 'and', 'rules': [{'left': '{{workflow.variables.stop}}', 'operator': 'boolean_equals', 'right': True}]}),
        node('body', 'set_variable', name='stop', value=True), node('done', 'log_event', message='Stopped early'),
    ], [edge('start', 'repeat'), edge('repeat', 'body', 'body'), edge('repeat', 'done', 'done')])
    early_exit['variables'] = {'stop': False}
    loop_conditions = graph([
        node('repeat', 'for_each', items=[5, 15, 2, 30], max_iterations=4),
        node('body', 'if_else', left='{{steps.repeat.output.value}}', operator='greater_than', right=10),
        node('yes', 'log_event', message='Above 10'), node('no', 'log_event', message='Below 10'), node('done', 'log_event', message='List processed'),
    ], [edge('start', 'repeat'), edge('repeat', 'body', 'body'), edge('body', 'yes', 'true'), edge('body', 'no', 'false'), edge('repeat', 'done', 'done')])
    and_module = condition_graph({'values': [True, False], 'operator': 'and'}, 'and_or')
    and_module['nodes'][1]['mappings'] = {'values': {'source': '{{trigger.input.flags}}', 'target_type': 'array'}}
    return [
        ('If and Else', simple, [({'amount': 1500}, 'yes'), ({'amount': 100}, 'no'), ({'amount': 1000}, 'yes')]),
        ('AND OR conditions', compound, [({'active': True, 'region': 'India', 'priority': 'Low'}, 'yes'), ({'active': True, 'region': 'UK', 'priority': 'High'}, 'yes'), ({'active': False, 'region': 'India', 'priority': 'High'}, 'no')]),
        ('For Each list', loop_graph(items='{{trigger.input.items}}', max_iterations=5), [({'items': ['A', 'B', 'C']}, 3), ({'items': []}, 0)]),
        ('Counted Loop', loop_graph('loop', max_iterations=3), [({}, 3)]),
        ('Nested Parallel Loops', nested, [({}, 4)]),
        ('Switch and Default', switch, [({'priority': 'high'}, 'high'), ({'priority': 'low'}, 'low'), ({'priority': 'other'}, 'fallback')]),
        ('Loop Early Exit', early_exit, [({}, 1)]),
        ('Conditions inside For Each', loop_conditions, [({}, {'yes': 2, 'no': 2})]),
        ('Compare Values', condition_graph({'left': '{{trigger.input.score}}', 'operator': 'greater_than', 'right': 10}, 'compare_values'), [({'score': 12}, 'yes'), ({'score': 10}, 'no')]),
        ('Check Empty', condition_graph({'value': '{{trigger.input.value}}'}, 'check_empty'), [({'value': None}, 'yes'), ({'value': []}, 'yes'), ({'value': 'filled'}, 'no')]),
        ('AND OR Module', and_module, [({'flags': [True, True]}, 'yes'), ({'flags': [True, False]}, 'no')]),
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scenario', action='append', default=[])
    parser.add_argument('--output', default='automation-logic-e2e.json')
    args = parser.parse_args()
    pending, results = [], []
    for name, definition, cases in scenarios():
        if args.scenario and name not in args.scenario:
            continue
        # Reuse the named example on re-runs; immutable published snapshots stay intact.
        rows = request('GET', '/power-apps/automations', params={'environment': 'development', 'search': 'E2E · ' + name}).get('items', [])
        row = next((r for r in rows if r['name'] == 'E2E · ' + name), None)
        if row:
            saved = request('GET', f'/power-apps/automations/{row["id"]}')
            expected_nodes = VisualWorkflowDefinition.model_validate(definition).model_dump()['nodes']
            signature = lambda items: sorted([{key: value for key, value in item.items() if key != 'position'} for item in items], key=lambda item: item['id'])
            if signature(saved['definition']['nodes']) != signature(expected_nodes) or saved['definition'].get('variables', {}) != definition.get('variables', {}):
                raise RuntimeError(f'Example {name} was modified; refusing to overwrite or execute changed logic')
            positions = {item['id']: item['position'] for item in definition['nodes']}
            if any(item['position'] != positions[item['id']] for item in saved['definition']['nodes']):
                state = request('GET', f'/power-apps/automations/{row["id"]}/runtime')
                if state['status'] == 'active':
                    request('POST', f'/power-apps/automations/{row["id"]}/runtime/pause', json={'expected_version': saved['version']})
                for item in saved['definition']['nodes']:
                    item['position'] = positions[item['id']]
                row = request('PUT', f'/power-apps/automations/{row["id"]}', json={'name': saved['name'], 'description': saved['description'], 'definition': saved['definition'], 'expected_version': saved['version']})
                for action in ['validate', 'publish', 'activate']:
                    request('POST', f'/power-apps/automations/{row["id"]}/runtime/{action}', json={'expected_version': row['version']})
        if not row:
            row = request('POST', '/power-apps/automations', json={'name': 'E2E · ' + name, 'description': 'Manual-only end-to-end example. No external messages or CRM changes.', 'definition': definition})
            for action in ['validate', 'publish', 'activate']:
                request('POST', f'/power-apps/automations/{row["id"]}/runtime/{action}', json={'expected_version': row['version']})
        for data, expected in cases:
            run = request('POST', f'/power-apps/automations/{row["id"]}/execute', json={'input': data, 'idempotency_key': 'logic-e2e-' + uuid.uuid4().hex})
            pending.append({'scenario': name, 'workflow_id': row['id'], 'run_id': run['id'], 'input': data, 'expected': expected})
        print(f'Started {name}: workflow #{row["id"]}', flush=True)
    deadline = time.monotonic() + 240
    while pending and time.monotonic() < deadline:
        for item in pending[:]:
            report = request('GET', f'/power-apps/executions/{item["run_id"]}')
            status = report['execution']['status']
            if status in {'completed', 'failed', 'cancelled', 'timed_out'}:
                completed = [s for s in report['steps'] if s['status'] == 'completed']
                if isinstance(item['expected'], dict):
                    actual = {key: sum(s['original_node_id'] == key for s in completed) for key in item['expected']}
                elif isinstance(item['expected'], int):
                    actual = len([s for s in completed if s['original_node_id'] == 'body'])
                else:
                    actual = next((s['original_node_id'] for s in completed if s['original_node_id'] in {'yes', 'no', 'high', 'low', 'fallback'}), None)
                logs = [e for e in report['events'] if e['kind'] == 'structured_log']
                result = {**item, 'status': status, 'actual': actual, 'visible_logs': len(logs), 'passed': status == 'completed' and actual == item['expected'] and bool(logs),
                          'errors': [s.get('error') for s in report['steps'] if s.get('error')]}
                results.append(result)
                pending.remove(item)
                print(json.dumps(result), flush=True)
        if pending:
            time.sleep(1)
    results.extend({**item, 'passed': False, 'status': 'timeout'} for item in pending)
    output = ROOT / '.local' / Path(args.output).name
    output.write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(f'{sum(r["passed"] for r in results)}/{len(results)} passed; report: {output}', flush=True)
    return 0 if results and all(r['passed'] for r in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
