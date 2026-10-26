"""Deterministic fictional Jira + Zephyr Squad-like dataset and event simulation."""
import argparse
import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / 'data' / 'historical'
EVENTS = ROOT / 'data' / 'simulations' / 'events.jsonl'
TEAMS = [('alpha','QAA','Payments'),('beta','QAB','Checkout'),('gamma','QAC','Mobile'),('delta','QAD','Backend APIs')]
BASE = date(2026, 7, 6)

def save_csv(name, rows, history_dir=None):
    target_history = history_dir or HISTORY
    target_history.mkdir(parents=True, exist_ok=True)
    with (target_history / name).open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

def generate(seed=42, history_dir=None):
    rng = random.Random(seed)
    sprints, issues, cases, cycles, executions, snapshots, dependencies = [], [], [], [], [], [], []
    for team, key, domain in TEAMS:
        for n in range(1, 7):
            start = BASE + timedelta(days=(n-1)*14)
            end = start + timedelta(days=13)
            sprint_id = f'{key}-SPR-{n:02d}'
            sprints.append(dict(team_id=team, project_key=key, sprint_id=sprint_id, sprint_number=n, start_date=start.isoformat(), end_date=end.isoformat(), goal=f'{domain} sprint {n} quality validation'))
            cycle_id = f'{key}-CYC-{n:02d}'
            cycles.append(dict(cycle_id=cycle_id, project_key=key, sprint_id=sprint_id, name=f'Sprint {n} regression'))
            for j in range(12):
                issue_key = f'{key}-{(n-1)*12+j+1}'
                kind = 'Bug' if j < 4 else 'Story'
                critical = kind == 'Bug' and j == 0 and team in ('beta','delta')
                status = ('Open' if critical and n >= 3 else rng.choice(['Done','In Progress','Open']))
                summary = f'{domain} {kind.lower()} {j+1} for sprint {n}'
                issues.append(dict(issue_key=issue_key, project_key=key, team_id=team, sprint_id=sprint_id, issue_type=kind, priority='Critical' if critical else rng.choice(['High','Medium','Low']), status=status, created_date=start.isoformat(), resolved_date=end.isoformat() if status=='Done' else '', blocked='true' if critical and status!='Done' else 'false', summary=summary))
            for j in range(15):
                test_id = f'{key}-TC-{j+1:03d}'
                if n == 1:
                    cases.append(dict(test_id=test_id, project_key=key, team_id=team, title=f'{domain} regression scenario {j+1}'))
                status = rng.choices(['PASS','FAIL','BLOCKED','NOT_EXECUTED'], weights=[75,12,8,5] if team not in ('beta','delta') else [62,20,12,6])[0]
                if team == 'beta' and j == 0 and n >= 3: status = 'BLOCKED'
                executions.append(dict(execution_id=f'{cycle_id}-EX-{j+1:03d}', project_key=key, team_id=team, sprint_id=sprint_id, cycle_id=cycle_id, test_id=test_id, status=status, executed_at=end.isoformat() if status!='NOT_EXECUTED' else ''))
            subset = [e for e in executions if e['sprint_id']==sprint_id]
            counts = {s:sum(e['status']==s for e in subset) for s in ['PASS','FAIL','BLOCKED','NOT_EXECUTED']}
            executed = counts['PASS']+counts['FAIL']+counts['BLOCKED']
            snapshots.append(dict(project_key=key, team_id=team, sprint_id=sprint_id, snapshot_date=end.isoformat(), total_tests=len(subset), passed=counts['PASS'], failed=counts['FAIL'], blocked=counts['BLOCKED'], not_executed=counts['NOT_EXECUTED'], pass_rate=round(100*counts['PASS']/executed,2) if executed else 0))
    # A persistent defect created in Sprint 2, linked to later sprint observations.
    issues.append(dict(issue_key='QAB-900', project_key='QAB', team_id='beta', sprint_id='QAB-SPR-02', issue_type='Bug', priority='Critical', status='Open', created_date=(BASE+timedelta(days=14)).isoformat(), resolved_date='', blocked='true', summary='Checkout payment authorization intermittently fails'))
    for n in range(2,7):
        dependencies.append(dict(source_issue='QAB-900', affected_project='QAB', observed_sprint=f'QAB-SPR-{n:02d}', dependency_type='carryover'))
    dependencies.append(dict(source_issue='QAD-37', affected_project='QAB', observed_sprint='QAB-SPR-04', dependency_type='cross_team'))
    for name, rows in [('sprints.csv',sprints),('jira_issues.csv',issues),('zephyr_test_cases.csv',cases),('zephyr_cycles.csv',cycles),('zephyr_executions.csv',executions),('snapshots.csv',snapshots),('dependencies.csv',dependencies)]: save_csv(name,rows,history_dir)
    print(f'Generated {len(sprints)} sprints, {len(issues)} issues, {len(cases)} test cases, {len(executions)} executions, {len(snapshots)} snapshots.')

def simulate(issue_key, status, note):
    issues_path = HISTORY / 'jira_issues.csv'
    if not issues_path.exists(): raise SystemExit('Generate baseline first.')
    with issues_path.open(newline='', encoding='utf-8') as f: rows = list(csv.DictReader(f))
    matches = [r for r in rows if r['issue_key']==issue_key]
    if not matches: raise SystemExit(f'Unknown issue: {issue_key}')
    EVENTS.parent.mkdir(parents=True,exist_ok=True)
    event = dict(event_id=sum(1 for _ in EVENTS.open(encoding='utf-8'))+1 if EVENTS.exists() else 1, issue_key=issue_key, project_key=matches[0]['project_key'], previous_baseline_status=matches[0]['status'], new_status=status, note=note, event_date=date.today().isoformat())
    with EVENTS.open('a',encoding='utf-8') as f: f.write(json.dumps(event)+'\n')
    print('Recorded simulation:',event)

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    sub=parser.add_subparsers(dest='command',required=True)
    g=sub.add_parser('generate'); g.add_argument('--seed',type=int,default=42)
    s=sub.add_parser('simulate'); s.add_argument('--issue',required=True); s.add_argument('--status',choices=['Open','In Progress','Done'],required=True); s.add_argument('--note',default='Manual simulation')
    args=parser.parse_args()
    if args.command=='generate':generate(args.seed)
    else:simulate(args.issue,args.status,args.note)
