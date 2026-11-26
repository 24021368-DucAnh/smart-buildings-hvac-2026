from team_tools.compare_bases import completion_status


def test_exhausted_budget_is_not_success():
    expected={('b/w','pid',8640),('b/w','pid_water',8640)}
    runs=[dict(scenario='b/w',policy='pid',steps=8640,exit_code=0)]
    assert completion_status(runs,expected)=='INCOMPLETE_BUDGET'
    runs.append(dict(scenario='b/w',policy='pid_water',steps=8640,exit_code=0))
    assert completion_status(runs,expected)=='SUCCEEDED'
    runs[-1]['exit_code']=1
    assert completion_status(runs,expected)=='FAILED'
