"""Project replies distinguish explicit names from conversation controls."""
import pytest
from app.ai_operator.conversational_actions import project_name


@pytest.mark.parametrize(('reply','expected'),[
    ('Use project "Customer Launch"','Customer Launch'),
    ("Use 'Customer Launch'",'Customer Launch'),
    ('Select “Customer Launch”.','Customer Launch'),
    ('Choose ‘Help Desk’','Help Desk'),
    ('project Create Website','Create Website'),
    ('"Help Desk"','Help Desk'),
    ('Customer Launch','Customer Launch'),
    ('yes please',None),
    ('cancel',None),
    ('create a task',None),
    ('project #123',None),
    ('123',None),
])
def test_explicit_project_name_replies(reply,expected):
    assert project_name(reply)==expected
