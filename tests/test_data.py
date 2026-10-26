import csv
from scripts import generate_data

def read(name):
    with (generate_data.HISTORY/name).open(newline='',encoding='utf-8') as f:
        return list(csv.DictReader(f))

def test_six_sprints_per_team(isolated_generator_history):
    generate_data.generate()
    rows=read('sprints.csv')
    assert len(rows)==24
    assert all(sum(r['team_id']==t for r in rows)==6 for t in ['alpha','beta','gamma','delta'])

def test_execution_references_are_valid(isolated_generator_history):
    generate_data.generate()
    cases={r['test_id'] for r in read('zephyr_test_cases.csv')}
    cycles={r['cycle_id'] for r in read('zephyr_cycles.csv')}
    assert all(r['test_id'] in cases and r['cycle_id'] in cycles for r in read('zephyr_executions.csv'))

def test_snapshots_balance(isolated_generator_history):
    generate_data.generate()
    for r in read('snapshots.csv'):
        assert int(r['total_tests'])==sum(int(r[k]) for k in ('passed','failed','blocked','not_executed'))
