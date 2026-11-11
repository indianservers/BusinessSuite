"""Dependency-free feature contract shared by TensorFlow training and local inference."""
import math
import re
from collections import Counter
from functools import lru_cache
from app.ai_operator.local_corpus import examples

STOP = set('please could can would you me the a an our us we do does is are to for of in on all every show list get display give find what which with named called by'.split())
SYNONYMS = {'todays':'today','today’s':'today','reminder':'reminders','job':'jobs','tasks':'task','leads':'lead','invoices':'invoice',
            'employees':'employee','projects':'project','overdue':'late','stuck':'blocked','missed':'late','coworkers':'employee',
            'opportunities':'deals','opportunity':'deals','accounts':'customers','staff':'employee','priorities':'priority'}


def head(text):
    return re.sub(r'^\s*(CRM|PMS|HRMS|HR|Sales|SRM)\s*:\s*','',text,flags=re.I)


def features(text):
    # Slot values must not teach the intent model that a particular customer,
    # task title or message body determines which operation was requested.
    command=head(text)
    command=re.sub(r'"[^"\n]*"|“[^”\n]*”',' value ',command)
    command=command.partition(':')[0]
    command=re.sub(r'#\s*\d+',' recordid ',command)
    words=[SYNONYMS.get(w,w) for w in re.findall(r'[a-z0-9]+',command.casefold().replace("'",'')) if w not in STOP]
    return Counter([*words,*(' '.join(pair) for pair in zip(words,words[1:]))])


@lru_cache(maxsize=1)
def fit():
    rows=examples();idf,vectors=fit_rows(rows)
    return rows,idf,vectors


def fit_rows(rows,max_vocabulary=None,feature_extractor=None):
    extractor=feature_extractor or features
    counts=[extractor(row['text']) for row in rows]
    df=Counter(term for row in counts for term in row)
    if max_vocabulary:
        base={term for row in examples() for term in features(row['text'])}
        keep=base | {term for term,_ in df.most_common(max(0,max_vocabulary-len(base))) if term not in base}
        df={term:n for term,n in df.items() if term in keep}
    idf={term:math.log((1+len(rows))/(1+count))+1 for term,count in df.items()}
    vectors=[]
    for count in counts:
        value={term:(1+math.log(n))*idf[term] for term,n in count.items() if term in idf}
        length=math.sqrt(sum(v*v for v in value.values())) or 1
        vectors.append({term:weight/length for term,weight in value.items()})
    return idf,vectors
