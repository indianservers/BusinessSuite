"""144 authored synthetic conversation-repair scenarios, with turn supervision."""
TITLES=['Review release checklist','Call the account contact','Investigate onboarding issue','Inspect access request',
        'Prepare delivery review','Review support response','Check acceptance notes','Arrange customer discussion']
HELP=['what does that mean?','which options are available?','what are my choices?','can you explain?',
      'explain this field','help me choose','I do not know','what should I enter?']
AMBIGUOUS=['yes','okay','ok','sure','no','approve','confirm','go ahead']
RENAME=['actually change title to {}','change the title to {}','set title to {}','update the title to {}',
        'title is {}','rename it to {}','call it {}','actually, name it {}']
CANCEL=['cancel this request','cancel the current action','discard this draft','stop this request',
        'cancel the proposed draft','end this operation','abandon this draft','stop the pending action']
PRIORITY=['not high, make it low','not high, set priority low','not high, use low priority','not high, change it to low',
          'not high, priority low','not high, low please','not high, set the priority to low','not high, mark as low priority']


def cases():
    result=[]
    for module,action in [('CRM','create a task'),('PMS','create a project task'),('HRMS','create an HR ticket')]:
        context={'project_id':1} if module=='PMS' else {}
        for i,title in enumerate(TITLES):
            initial=f'{module}: {action}'
            ready=f'{initial} "Original review"'
            for kind,reply in [('clarify',HELP[i]),('ambiguous',AMBIGUOUS[i]),('rename',RENAME[i].format(title)),
                               ('correct_priority',PRIORITY[i]),('cancel',CANCEL[i]),('date_before_title','tomorrow')]:
                messages=[ready if kind in {'rename','correct_priority','cancel'} else initial]
                if kind=='correct_priority':messages[0]+=' high priority'
                messages.append(reply)
                if kind in {'clarify','ambiguous','date_before_title'}:messages.append(title)
                expected='cancelled' if kind=='cancel' else 'review_required'
                field='subject' if module=='HRMS' else 'title'
                values={} if kind=='cancel' else {field:'Original review' if kind=='correct_priority' else title}
                if kind=='correct_priority':values['priority']='Low'
                result.append({'id':f'{module}-repair-{kind}-{i}','module':module,'kind':'repair','repair':kind,'context':context,
                    'messages':messages,'expected':expected,'expected_payload':values,
                    'supervision':{'intent':'ticket.create' if module=='HRMS' else 'tasks.create',
                        'pending':'_approval' if kind in {'rename','correct_priority','cancel'} else 'title',
                        'text':reply,'act':'clarify' if kind in {'clarify','ambiguous'} else 'cancel_action' if kind=='cancel' else 'provide_value'}})
    return result
