"""Frozen code-owned actor17/121 release contract. No model/event/runtime imports.

Generated from reviewed static schema sources; changing this is a release review.
"""

CONTRACT = {'guard_specs': [['business_pack_record_ownership',
                  'suite_pack_anchor',
                  ['id',
                   'company_id',
                   'branch_id',
                   'context_id',
                   'resource_table',
                   'resource_key',
                   'source',
                   'revision',
                   'created_at'],
                  [],
                  None],
                 ['business_pack_delivery_sources',
                  'suite_pack_delivery',
                  ['id',
                   'email_outbox_id',
                   'notification_id',
                   'company_id',
                   'branch_id',
                   'context_id',
                   'pack_key',
                   'pack_version',
                   'source_table',
                   'source_key',
                   'source_kind',
                   'module',
                   'actor_user_id',
                   'recipient_user_id',
                   'recipient_email',
                   'payload_sha256',
                   'created_at'],
                  [],
                  None],
                 ['email_outbox',
                  'suite_private_email',
                  ['id',
                   'event_key',
                   'organization_id',
                   'module',
                   'recipient_user_id',
                   'recipient',
                   'subject',
                   'body',
                   'is_html',
                   'created_at'],
                  ['status', 'provider_message_id', 'error', 'attempts', 'accepted_at'],
                  'email_outbox_id'],
                 ['notifications',
                  'suite_private_notice',
                  ['id',
                   'company_id',
                   'user_id',
                   'title',
                   'message',
                   'module',
                   'event_type',
                   'related_entity_type',
                   'related_entity_id',
                   'action_url',
                   'priority',
                   'channels',
                   'created_at'],
                  ['is_read', 'read_at'],
                  'notification_id']],
 'owner_migration_sha256': '8ddeaf8436d3a3935b8ae182c7bccd4f0a800436556023c2669e3db75c0e2fdf',
 'owner_model_sha256': '6a6dd616e1bdbfeee8e45cce615efab9769d4745834742cc3e996b537cb00865',
 'postgresql_functions': {'suite_pack_anchor_guard': '\n'
                                                     '            BEGIN\n'
                                                     "              IF TG_OP='TRUNCATE' THEN\n"
                                                     '                IF EXISTS(SELECT 1 FROM '
                                                     'business_pack_record_ownership WHERE TRUE LIMIT 1) THEN\n'
                                                     "                  RAISE EXCEPTION 'Private delivery history "
                                                     "must be retained' USING ERRCODE='23514';\n"
                                                     '                END IF;\n'
                                                     '                RETURN NULL;\n'
                                                     '              END IF;\n'
                                                     "              IF TG_OP='DELETE' THEN\n"
                                                     '                IF TRUE THEN\n'
                                                     "                  RAISE EXCEPTION 'Private delivery history "
                                                     "must be retained' USING ERRCODE='23514';\n"
                                                     '                END IF;\n'
                                                     '                RETURN OLD;\n'
                                                     '              END IF;\n'
                                                     '              IF (TRUE) AND (NEW.id IS DISTINCT FROM OLD.id '
                                                     'OR NEW.company_id IS DISTINCT FROM OLD.company_id OR '
                                                     'NEW.branch_id IS DISTINCT FROM OLD.branch_id OR '
                                                     'NEW.context_id IS DISTINCT FROM OLD.context_id OR '
                                                     'NEW.resource_table IS DISTINCT FROM OLD.resource_table OR '
                                                     'NEW.resource_key IS DISTINCT FROM OLD.resource_key OR '
                                                     'NEW.source IS DISTINCT FROM OLD.source OR NEW.revision IS '
                                                     'DISTINCT FROM OLD.revision OR NEW.created_at IS DISTINCT '
                                                     'FROM OLD.created_at) THEN\n'
                                                     "                RAISE EXCEPTION 'Private delivery source "
                                                     "and payload are immutable' USING ERRCODE='23514';\n"
                                                     '              END IF;\n'
                                                     '              RETURN NEW;\n'
                                                     '            END; ',
                          'suite_pack_delivery_guard': '\n'
                                                       '            BEGIN\n'
                                                       "              IF TG_OP='TRUNCATE' THEN\n"
                                                       '                IF EXISTS(SELECT 1 FROM '
                                                       'business_pack_delivery_sources WHERE TRUE LIMIT 1) THEN\n'
                                                       "                  RAISE EXCEPTION 'Private delivery "
                                                       "history must be retained' USING ERRCODE='23514';\n"
                                                       '                END IF;\n'
                                                       '                RETURN NULL;\n'
                                                       '              END IF;\n'
                                                       "              IF TG_OP='DELETE' THEN\n"
                                                       '                IF TRUE THEN\n'
                                                       "                  RAISE EXCEPTION 'Private delivery "
                                                       "history must be retained' USING ERRCODE='23514';\n"
                                                       '                END IF;\n'
                                                       '                RETURN OLD;\n'
                                                       '              END IF;\n'
                                                       '              IF (TRUE) AND (NEW.id IS DISTINCT FROM '
                                                       'OLD.id OR NEW.email_outbox_id IS DISTINCT FROM '
                                                       'OLD.email_outbox_id OR NEW.notification_id IS DISTINCT '
                                                       'FROM OLD.notification_id OR NEW.company_id IS DISTINCT '
                                                       'FROM OLD.company_id OR NEW.branch_id IS DISTINCT FROM '
                                                       'OLD.branch_id OR NEW.context_id IS DISTINCT FROM '
                                                       'OLD.context_id OR NEW.pack_key IS DISTINCT FROM '
                                                       'OLD.pack_key OR NEW.pack_version IS DISTINCT FROM '
                                                       'OLD.pack_version OR NEW.source_table IS DISTINCT FROM '
                                                       'OLD.source_table OR NEW.source_key IS DISTINCT FROM '
                                                       'OLD.source_key OR NEW.source_kind IS DISTINCT FROM '
                                                       'OLD.source_kind OR NEW.module IS DISTINCT FROM OLD.module '
                                                       'OR NEW.actor_user_id IS DISTINCT FROM OLD.actor_user_id '
                                                       'OR NEW.recipient_user_id IS DISTINCT FROM '
                                                       'OLD.recipient_user_id OR NEW.recipient_email IS DISTINCT '
                                                       'FROM OLD.recipient_email OR NEW.payload_sha256 IS '
                                                       'DISTINCT FROM OLD.payload_sha256 OR NEW.created_at IS '
                                                       'DISTINCT FROM OLD.created_at) THEN\n'
                                                       "                RAISE EXCEPTION 'Private delivery source "
                                                       "and payload are immutable' USING ERRCODE='23514';\n"
                                                       '              END IF;\n'
                                                       '              RETURN NEW;\n'
                                                       '            END; ',
                          'suite_private_email_guard': '\n'
                                                       '            BEGIN\n'
                                                       "              IF TG_OP='TRUNCATE' THEN\n"
                                                       '                IF EXISTS(SELECT 1 FROM email_outbox '
                                                       'WHERE EXISTS(SELECT 1 FROM business_pack_delivery_sources '
                                                       'd WHERE d.email_outbox_id IS NOT NULL) LIMIT 1) THEN\n'
                                                       "                  RAISE EXCEPTION 'Private delivery "
                                                       "history must be retained' USING ERRCODE='23514';\n"
                                                       '                END IF;\n'
                                                       '                RETURN NULL;\n'
                                                       '              END IF;\n'
                                                       "              IF TG_OP='DELETE' THEN\n"
                                                       '                IF EXISTS(SELECT 1 FROM '
                                                       'business_pack_delivery_sources d WHERE '
                                                       'd.email_outbox_id=OLD.id) THEN\n'
                                                       "                  RAISE EXCEPTION 'Private delivery "
                                                       "history must be retained' USING ERRCODE='23514';\n"
                                                       '                END IF;\n'
                                                       '                RETURN OLD;\n'
                                                       '              END IF;\n'
                                                       '              IF (EXISTS(SELECT 1 FROM '
                                                       'business_pack_delivery_sources d WHERE '
                                                       'd.email_outbox_id=OLD.id)) AND (NEW.id IS DISTINCT FROM '
                                                       'OLD.id OR NEW.event_key IS DISTINCT FROM OLD.event_key OR '
                                                       'NEW.organization_id IS DISTINCT FROM OLD.organization_id '
                                                       'OR NEW.module IS DISTINCT FROM OLD.module OR '
                                                       'NEW.recipient_user_id IS DISTINCT FROM '
                                                       'OLD.recipient_user_id OR NEW.recipient IS DISTINCT FROM '
                                                       'OLD.recipient OR NEW.subject IS DISTINCT FROM OLD.subject '
                                                       'OR NEW.body IS DISTINCT FROM OLD.body OR NEW.is_html IS '
                                                       'DISTINCT FROM OLD.is_html OR NEW.created_at IS DISTINCT '
                                                       'FROM OLD.created_at) THEN\n'
                                                       "                RAISE EXCEPTION 'Private delivery source "
                                                       "and payload are immutable' USING ERRCODE='23514';\n"
                                                       '              END IF;\n'
                                                       '              RETURN NEW;\n'
                                                       '            END; ',
                          'suite_private_notice_guard': '\n'
                                                        '            BEGIN\n'
                                                        "              IF TG_OP='TRUNCATE' THEN\n"
                                                        '                IF EXISTS(SELECT 1 FROM notifications '
                                                        'WHERE EXISTS(SELECT 1 FROM '
                                                        'business_pack_delivery_sources d WHERE d.notification_id '
                                                        'IS NOT NULL) LIMIT 1) THEN\n'
                                                        "                  RAISE EXCEPTION 'Private delivery "
                                                        "history must be retained' USING ERRCODE='23514';\n"
                                                        '                END IF;\n'
                                                        '                RETURN NULL;\n'
                                                        '              END IF;\n'
                                                        "              IF TG_OP='DELETE' THEN\n"
                                                        '                IF EXISTS(SELECT 1 FROM '
                                                        'business_pack_delivery_sources d WHERE '
                                                        'd.notification_id=OLD.id) THEN\n'
                                                        "                  RAISE EXCEPTION 'Private delivery "
                                                        "history must be retained' USING ERRCODE='23514';\n"
                                                        '                END IF;\n'
                                                        '                RETURN OLD;\n'
                                                        '              END IF;\n'
                                                        '              IF (EXISTS(SELECT 1 FROM '
                                                        'business_pack_delivery_sources d WHERE '
                                                        'd.notification_id=OLD.id)) AND (NEW.id IS DISTINCT FROM '
                                                        'OLD.id OR NEW.company_id IS DISTINCT FROM OLD.company_id '
                                                        'OR NEW.user_id IS DISTINCT FROM OLD.user_id OR NEW.title '
                                                        'IS DISTINCT FROM OLD.title OR NEW.message IS DISTINCT '
                                                        'FROM OLD.message OR NEW.module IS DISTINCT FROM '
                                                        'OLD.module OR NEW.event_type IS DISTINCT FROM '
                                                        'OLD.event_type OR NEW.related_entity_type IS DISTINCT '
                                                        'FROM OLD.related_entity_type OR NEW.related_entity_id IS '
                                                        'DISTINCT FROM OLD.related_entity_id OR NEW.action_url IS '
                                                        'DISTINCT FROM OLD.action_url OR NEW.priority IS DISTINCT '
                                                        'FROM OLD.priority OR CAST(NEW.channels AS TEXT) IS '
                                                        'DISTINCT FROM CAST(OLD.channels AS TEXT) OR '
                                                        'NEW.created_at IS DISTINCT FROM OLD.created_at) THEN\n'
                                                        "                RAISE EXCEPTION 'Private delivery source "
                                                        "and payload are immutable' USING ERRCODE='23514';\n"
                                                        '              END IF;\n'
                                                        '              RETURN NEW;\n'
                                                        '            END; '},
 'revision': 'pg_20261116_121_delivery_sources',
 'sqlite_triggers': {'suite_pack_anchor_immutable': 'CREATE TRIGGER suite_pack_anchor_immutable\n'
                                                    '                BEFORE UPDATE ON '
                                                    'business_pack_record_ownership WHEN (TRUE) AND (NEW.id IS '
                                                    'NOT OLD.id OR NEW.company_id IS NOT OLD.company_id OR '
                                                    'NEW.branch_id IS NOT OLD.branch_id OR NEW.context_id IS NOT '
                                                    'OLD.context_id OR NEW.resource_table IS NOT '
                                                    'OLD.resource_table OR NEW.resource_key IS NOT '
                                                    'OLD.resource_key OR NEW.source IS NOT OLD.source OR '
                                                    'NEW.revision IS NOT OLD.revision OR NEW.created_at IS NOT '
                                                    'OLD.created_at)\n'
                                                    "                BEGIN SELECT RAISE(ABORT,'Private delivery "
                                                    "source and payload are immutable'); END",
                     'suite_pack_anchor_retained': 'CREATE TRIGGER suite_pack_anchor_retained\n'
                                                   '                BEFORE DELETE ON '
                                                   'business_pack_record_ownership WHEN (TRUE)\n'
                                                   "                BEGIN SELECT RAISE(ABORT,'Private delivery "
                                                   "source and payload must be retained'); END",
                     'suite_pack_delivery_immutable': 'CREATE TRIGGER suite_pack_delivery_immutable\n'
                                                      '                BEFORE UPDATE ON '
                                                      'business_pack_delivery_sources WHEN (TRUE) AND (NEW.id IS '
                                                      'NOT OLD.id OR NEW.email_outbox_id IS NOT '
                                                      'OLD.email_outbox_id OR NEW.notification_id IS NOT '
                                                      'OLD.notification_id OR NEW.company_id IS NOT '
                                                      'OLD.company_id OR NEW.branch_id IS NOT OLD.branch_id OR '
                                                      'NEW.context_id IS NOT OLD.context_id OR NEW.pack_key IS '
                                                      'NOT OLD.pack_key OR NEW.pack_version IS NOT '
                                                      'OLD.pack_version OR NEW.source_table IS NOT '
                                                      'OLD.source_table OR NEW.source_key IS NOT OLD.source_key '
                                                      'OR NEW.source_kind IS NOT OLD.source_kind OR NEW.module IS '
                                                      'NOT OLD.module OR NEW.actor_user_id IS NOT '
                                                      'OLD.actor_user_id OR NEW.recipient_user_id IS NOT '
                                                      'OLD.recipient_user_id OR NEW.recipient_email IS NOT '
                                                      'OLD.recipient_email OR NEW.payload_sha256 IS NOT '
                                                      'OLD.payload_sha256 OR NEW.created_at IS NOT '
                                                      'OLD.created_at)\n'
                                                      "                BEGIN SELECT RAISE(ABORT,'Private delivery "
                                                      "source and payload are immutable'); END",
                     'suite_pack_delivery_retained': 'CREATE TRIGGER suite_pack_delivery_retained\n'
                                                     '                BEFORE DELETE ON '
                                                     'business_pack_delivery_sources WHEN (TRUE)\n'
                                                     "                BEGIN SELECT RAISE(ABORT,'Private delivery "
                                                     "source and payload must be retained'); END",
                     'suite_private_email_immutable': 'CREATE TRIGGER suite_private_email_immutable\n'
                                                      '                BEFORE UPDATE ON email_outbox WHEN '
                                                      '(EXISTS(SELECT 1 FROM business_pack_delivery_sources d '
                                                      'WHERE d.email_outbox_id=OLD.id)) AND (NEW.id IS NOT OLD.id '
                                                      'OR NEW.event_key IS NOT OLD.event_key OR '
                                                      'NEW.organization_id IS NOT OLD.organization_id OR '
                                                      'NEW.module IS NOT OLD.module OR NEW.recipient_user_id IS '
                                                      'NOT OLD.recipient_user_id OR NEW.recipient IS NOT '
                                                      'OLD.recipient OR NEW.subject IS NOT OLD.subject OR '
                                                      'NEW.body IS NOT OLD.body OR NEW.is_html IS NOT OLD.is_html '
                                                      'OR NEW.created_at IS NOT OLD.created_at)\n'
                                                      "                BEGIN SELECT RAISE(ABORT,'Private delivery "
                                                      "source and payload are immutable'); END",
                     'suite_private_email_retained': 'CREATE TRIGGER suite_private_email_retained\n'
                                                     '                BEFORE DELETE ON email_outbox WHEN '
                                                     '(EXISTS(SELECT 1 FROM business_pack_delivery_sources d '
                                                     'WHERE d.email_outbox_id=OLD.id))\n'
                                                     "                BEGIN SELECT RAISE(ABORT,'Private delivery "
                                                     "source and payload must be retained'); END",
                     'suite_private_notice_immutable': 'CREATE TRIGGER suite_private_notice_immutable\n'
                                                       '                BEFORE UPDATE ON notifications WHEN '
                                                       '(EXISTS(SELECT 1 FROM business_pack_delivery_sources d '
                                                       'WHERE d.notification_id=OLD.id)) AND (NEW.id IS NOT '
                                                       'OLD.id OR NEW.company_id IS NOT OLD.company_id OR '
                                                       'NEW.user_id IS NOT OLD.user_id OR NEW.title IS NOT '
                                                       'OLD.title OR NEW.message IS NOT OLD.message OR NEW.module '
                                                       'IS NOT OLD.module OR NEW.event_type IS NOT OLD.event_type '
                                                       'OR NEW.related_entity_type IS NOT OLD.related_entity_type '
                                                       'OR NEW.related_entity_id IS NOT OLD.related_entity_id OR '
                                                       'NEW.action_url IS NOT OLD.action_url OR NEW.priority IS '
                                                       'NOT OLD.priority OR NEW.channels IS NOT OLD.channels OR '
                                                       'NEW.created_at IS NOT OLD.created_at)\n'
                                                       "                BEGIN SELECT RAISE(ABORT,'Private "
                                                       "delivery source and payload are immutable'); END",
                     'suite_private_notice_retained': 'CREATE TRIGGER suite_private_notice_retained\n'
                                                      '                BEFORE DELETE ON notifications WHEN '
                                                      '(EXISTS(SELECT 1 FROM business_pack_delivery_sources d '
                                                      'WHERE d.notification_id=OLD.id))\n'
                                                      "                BEGIN SELECT RAISE(ABORT,'Private delivery "
                                                      "source and payload must be retained'); END"},
 'tables': {'postgresql': {'business_pack_activations': {'checks': {'ck_pack_activation_key': 'length(trim(pack_key)) '
                                                                                              'BETWEEN 1 AND 64',
                                                                    'ck_pack_activation_revision': 'revision > 0',
                                                                    'ck_pack_activation_state': 'state IN '
                                                                                                "('draft','active','suspended','retired')",
                                                                    'ck_pack_activation_version': 'pack_version > '
                                                                                                  '0'},
                                                         'columns': {'company_id': ('INTEGER', False),
                                                                     'created_at': ('TIMESTAMP WITH TIME ZONE',
                                                                                    False),
                                                                     'id': ('INTEGER', False),
                                                                     'pack_key': ('VARCHAR(64)', False),
                                                                     'pack_version': ('INTEGER', False),
                                                                     'revision': ('INTEGER', False),
                                                                     'state': ('VARCHAR(20)', False),
                                                                     'updated_at': ('TIMESTAMP WITH TIME ZONE',
                                                                                    False)},
                                                         'foreign_keys': [(('company_id',),
                                                                           'companies',
                                                                           ('id',),
                                                                           'RESTRICT',
                                                                           False,
                                                                           False)],
                                                         'pk': ('id',),
                                                         'unique': [('id',
                                                                     'company_id',
                                                                     'pack_key',
                                                                     'pack_version'),
                                                                    ('company_id', 'pack_key', 'pack_version')]},
                           'business_pack_contexts': {'checks': {'ck_pack_context_key': 'length(trim(pack_key)) '
                                                                                        'BETWEEN 1 AND 64',
                                                                 'ck_pack_context_revision': 'revision > 0',
                                                                 'ck_pack_context_state': 'state IN '
                                                                                          "('draft','active','suspended','retired')",
                                                                 'ck_pack_context_version': 'pack_version > 0'},
                                                      'columns': {'activation_id': ('INTEGER', False),
                                                                  'branch_id': ('INTEGER', False),
                                                                  'company_id': ('INTEGER', False),
                                                                  'created_at': ('TIMESTAMP WITH TIME ZONE',
                                                                                 False),
                                                                  'ever_activated': ('BOOLEAN', False),
                                                                  'id': ('INTEGER', False),
                                                                  'pack_key': ('VARCHAR(64)', False),
                                                                  'pack_version': ('INTEGER', False),
                                                                  'revision': ('INTEGER', False),
                                                                  'state': ('VARCHAR(20)', False),
                                                                  'updated_at': ('TIMESTAMP WITH TIME ZONE',
                                                                                 False)},
                                                      'foreign_keys': [(('company_id',),
                                                                        'companies',
                                                                        ('id',),
                                                                        'RESTRICT',
                                                                        False,
                                                                        False),
                                                                       (('branch_id',),
                                                                        'branches',
                                                                        ('id',),
                                                                        'RESTRICT',
                                                                        False,
                                                                        False),
                                                                       (('activation_id',
                                                                         'company_id',
                                                                         'pack_key',
                                                                         'pack_version'),
                                                                        'business_pack_activations',
                                                                        ('id',
                                                                         'company_id',
                                                                         'pack_key',
                                                                         'pack_version'),
                                                                        'RESTRICT',
                                                                        False,
                                                                        False)],
                                                      'pk': ('id',),
                                                      'unique': [('id', 'company_id', 'branch_id'),
                                                                 ('activation_id', 'branch_id')]},
                           'business_pack_delivery_sources': {'checks': {'ck_pack_delivery_payload': 'length(payload_sha256)=64 '
                                                                                                     'AND '
                                                                                                     'length(source_key)>0',
                                                                         'ck_pack_delivery_scope': 'company_id > '
                                                                                                   '0 AND '
                                                                                                   'branch_id > 0 '
                                                                                                   'AND '
                                                                                                   'context_id > '
                                                                                                   '0 AND '
                                                                                                   'pack_version '
                                                                                                   '> 0 AND '
                                                                                                   'actor_user_id '
                                                                                                   '> 0',
                                                                         'ck_pack_delivery_target': '(email_outbox_id '
                                                                                                    'IS NOT NULL '
                                                                                                    'AND '
                                                                                                    'notification_id '
                                                                                                    'IS NULL) OR '
                                                                                                    '(email_outbox_id '
                                                                                                    'IS NULL AND '
                                                                                                    'notification_id '
                                                                                                    'IS NOT '
                                                                                                    'NULL)'},
                                                              'columns': {'actor_user_id': ('INTEGER', False),
                                                                          'branch_id': ('INTEGER', False),
                                                                          'company_id': ('INTEGER', False),
                                                                          'context_id': ('INTEGER', False),
                                                                          'created_at': ('TIMESTAMP WITH TIME '
                                                                                         'ZONE',
                                                                                         False),
                                                                          'email_outbox_id': ('INTEGER', True),
                                                                          'id': ('INTEGER', False),
                                                                          'module': ('VARCHAR(60)', False),
                                                                          'notification_id': ('INTEGER', True),
                                                                          'pack_key': ('VARCHAR(60)', False),
                                                                          'pack_version': ('INTEGER', False),
                                                                          'payload_sha256': ('VARCHAR(64)', False),
                                                                          'recipient_email': ('VARCHAR(254)',
                                                                                              True),
                                                                          'recipient_user_id': ('INTEGER', True),
                                                                          'source_key': ('VARCHAR(500)', False),
                                                                          'source_kind': ('VARCHAR(40)', False),
                                                                          'source_table': ('VARCHAR(120)', False)},
                                                              'foreign_keys': [(('email_outbox_id',),
                                                                                'email_outbox',
                                                                                ('id',),
                                                                                'RESTRICT',
                                                                                False,
                                                                                False),
                                                                               (('actor_user_id',),
                                                                                'users',
                                                                                ('id',),
                                                                                'RESTRICT',
                                                                                False,
                                                                                False),
                                                                               (('context_id',
                                                                                 'company_id',
                                                                                 'branch_id'),
                                                                                'business_pack_contexts',
                                                                                ('id', 'company_id', 'branch_id'),
                                                                                'RESTRICT',
                                                                                False,
                                                                                False),
                                                                               (('notification_id',),
                                                                                'notifications',
                                                                                ('id',),
                                                                                'RESTRICT',
                                                                                False,
                                                                                False),
                                                                               (('recipient_user_id',),
                                                                                'users',
                                                                                ('id',),
                                                                                'RESTRICT',
                                                                                False,
                                                                                False)],
                                                              'pk': ('id',),
                                                              'unique': [('email_outbox_id',),
                                                                         ('notification_id',)]},
                           'business_pack_master_availability': {'checks': {'ck_pack_master_key': 'length(trim(resource_key)) '
                                                                                                  'BETWEEN 1 AND '
                                                                                                  '500',
                                                                            'ck_pack_master_revision': 'revision '
                                                                                                       '> 0',
                                                                            'ck_pack_master_table': 'length(trim(resource_table)) '
                                                                                                    'BETWEEN 1 '
                                                                                                    'AND 120'},
                                                                 'columns': {'active': ('BOOLEAN', False),
                                                                             'branch_id': ('INTEGER', False),
                                                                             'company_id': ('INTEGER', False),
                                                                             'context_id': ('INTEGER', False),
                                                                             'created_at': ('TIMESTAMP WITH TIME '
                                                                                            'ZONE',
                                                                                            False),
                                                                             'id': ('INTEGER', False),
                                                                             'resource_key': ('VARCHAR(500)',
                                                                                              False),
                                                                             'resource_table': ('VARCHAR(120)',
                                                                                                False),
                                                                             'revision': ('INTEGER', False),
                                                                             'updated_at': ('TIMESTAMP WITH TIME '
                                                                                            'ZONE',
                                                                                            False)},
                                                                 'foreign_keys': [(('branch_id',),
                                                                                   'branches',
                                                                                   ('id',),
                                                                                   'RESTRICT',
                                                                                   False,
                                                                                   False),
                                                                                  (('context_id',
                                                                                    'company_id',
                                                                                    'branch_id'),
                                                                                   'business_pack_contexts',
                                                                                   ('id',
                                                                                    'company_id',
                                                                                    'branch_id'),
                                                                                   'RESTRICT',
                                                                                   False,
                                                                                   False),
                                                                                  (('company_id',),
                                                                                   'companies',
                                                                                   ('id',),
                                                                                   'RESTRICT',
                                                                                   False,
                                                                                   False)],
                                                                 'pk': ('id',),
                                                                 'unique': [('context_id',
                                                                             'resource_table',
                                                                             'resource_key')]},
                           'business_pack_record_ownership': {'checks': {'ck_pack_record_key': 'length(trim(resource_key)) '
                                                                                               'BETWEEN 1 AND 500',
                                                                         'ck_pack_record_revision': 'revision > 0',
                                                                         'ck_pack_record_source': 'length(trim(source)) '
                                                                                                  'BETWEEN 1 AND '
                                                                                                  '80',
                                                                         'ck_pack_record_table': 'length(trim(resource_table)) '
                                                                                                 'BETWEEN 1 AND '
                                                                                                 '120'},
                                                              'columns': {'branch_id': ('INTEGER', False),
                                                                          'company_id': ('INTEGER', False),
                                                                          'context_id': ('INTEGER', False),
                                                                          'created_at': ('TIMESTAMP WITH TIME '
                                                                                         'ZONE',
                                                                                         False),
                                                                          'id': ('INTEGER', False),
                                                                          'resource_key': ('VARCHAR(500)', False),
                                                                          'resource_table': ('VARCHAR(120)',
                                                                                             False),
                                                                          'revision': ('INTEGER', False),
                                                                          'source': ('VARCHAR(80)', False)},
                                                              'foreign_keys': [(('company_id',),
                                                                                'companies',
                                                                                ('id',),
                                                                                'RESTRICT',
                                                                                False,
                                                                                False),
                                                                               (('branch_id',),
                                                                                'branches',
                                                                                ('id',),
                                                                                'RESTRICT',
                                                                                False,
                                                                                False),
                                                                               (('context_id',
                                                                                 'company_id',
                                                                                 'branch_id'),
                                                                                'business_pack_contexts',
                                                                                ('id', 'company_id', 'branch_id'),
                                                                                'RESTRICT',
                                                                                False,
                                                                                False)],
                                                              'pk': ('id',),
                                                              'unique': [('resource_table', 'resource_key')]},
                           'business_pack_user_grants': {'checks': {'ck_pack_user_grant_revision': 'revision > 0',
                                                                    'ck_pack_user_grant_role': 'length(trim(role)) '
                                                                                               'BETWEEN 1 AND 64'},
                                                         'columns': {'active': ('BOOLEAN', False),
                                                                     'branch_id': ('INTEGER', False),
                                                                     'company_id': ('INTEGER', False),
                                                                     'context_id': ('INTEGER', False),
                                                                     'created_at': ('TIMESTAMP WITH TIME ZONE',
                                                                                    False),
                                                                     'id': ('INTEGER', False),
                                                                     'revision': ('INTEGER', False),
                                                                     'role': ('VARCHAR(64)', False),
                                                                     'updated_at': ('TIMESTAMP WITH TIME ZONE',
                                                                                    False),
                                                                     'user_id': ('INTEGER', False)},
                                                         'foreign_keys': [(('user_id',),
                                                                           'users',
                                                                           ('id',),
                                                                           'RESTRICT',
                                                                           False,
                                                                           False),
                                                                          (('company_id',),
                                                                           'companies',
                                                                           ('id',),
                                                                           'RESTRICT',
                                                                           False,
                                                                           False),
                                                                          (('context_id',
                                                                            'company_id',
                                                                            'branch_id'),
                                                                           'business_pack_contexts',
                                                                           ('id', 'company_id', 'branch_id'),
                                                                           'RESTRICT',
                                                                           False,
                                                                           False),
                                                                          (('branch_id',),
                                                                           'branches',
                                                                           ('id',),
                                                                           'RESTRICT',
                                                                           False,
                                                                           False)],
                                                         'pk': ('id',),
                                                         'unique': [('context_id', 'user_id')]},
                           'email_outbox': {'checks': {},
                                            'columns': {'accepted_at': ('TIMESTAMP WITH TIME ZONE', True),
                                                        'attempts': ('INTEGER', False),
                                                        'body': ('TEXT', False),
                                                        'created_at': ('TIMESTAMP WITH TIME ZONE', True),
                                                        'error': ('VARCHAR(240)', True),
                                                        'event_key': ('VARCHAR(180)', False),
                                                        'id': ('INTEGER', False),
                                                        'is_html': ('BOOLEAN', False),
                                                        'module': ('VARCHAR(60)', False),
                                                        'organization_id': ('INTEGER', True),
                                                        'provider_message_id': ('VARCHAR(200)', True),
                                                        'recipient': ('VARCHAR(254)', False),
                                                        'recipient_user_id': ('INTEGER', True),
                                                        'status': ('VARCHAR(30)', False),
                                                        'subject': ('VARCHAR(240)', False)},
                                            'foreign_keys': [],
                                            'pk': ('id',),
                                            'unique': [('event_key',)]},
                           'notifications': {'checks': {},
                                             'columns': {'action_url': ('VARCHAR(500)', True),
                                                         'channels': ('JSON', True),
                                                         'company_id': ('INTEGER', True),
                                                         'created_at': ('TIMESTAMP WITH TIME ZONE', True),
                                                         'event_type': ('VARCHAR(80)', True),
                                                         'id': ('INTEGER', False),
                                                         'is_read': ('BOOLEAN', True),
                                                         'message': ('TEXT', False),
                                                         'module': ('VARCHAR(50)', True),
                                                         'priority': ('VARCHAR(20)', True),
                                                         'read_at': ('TIMESTAMP WITH TIME ZONE', True),
                                                         'related_entity_id': ('INTEGER', True),
                                                         'related_entity_type': ('VARCHAR(80)', True),
                                                         'title': ('VARCHAR(200)', False),
                                                         'user_id': ('INTEGER', False)},
                                             'foreign_keys': [(('company_id',),
                                                               'companies',
                                                               ('id',),
                                                               'SET NULL',
                                                               False,
                                                               False),
                                                              (('user_id',),
                                                               'users',
                                                               ('id',),
                                                               'CASCADE',
                                                               False,
                                                               False)],
                                             'pk': ('id',),
                                             'unique': []}},
            'sqlite': {'business_pack_activations': {'checks': {'ck_pack_activation_key': 'length(trim(pack_key)) '
                                                                                          'BETWEEN 1 AND 64',
                                                                'ck_pack_activation_revision': 'revision > 0',
                                                                'ck_pack_activation_state': 'state IN '
                                                                                            "('draft','active','suspended','retired')",
                                                                'ck_pack_activation_version': 'pack_version > 0'},
                                                     'columns': {'company_id': ('INTEGER', False),
                                                                 'created_at': ('DATETIME', False),
                                                                 'id': ('INTEGER', False),
                                                                 'pack_key': ('VARCHAR(64)', False),
                                                                 'pack_version': ('INTEGER', False),
                                                                 'revision': ('INTEGER', False),
                                                                 'state': ('VARCHAR(20)', False),
                                                                 'updated_at': ('DATETIME', False)},
                                                     'foreign_keys': [(('company_id',),
                                                                       'companies',
                                                                       ('id',),
                                                                       'RESTRICT',
                                                                       False,
                                                                       False)],
                                                     'pk': ('id',),
                                                     'unique': [('id', 'company_id', 'pack_key', 'pack_version'),
                                                                ('company_id', 'pack_key', 'pack_version')]},
                       'business_pack_contexts': {'checks': {'ck_pack_context_ever_activated': 'ever_activated IN '
                                                                                               '(0, 1)',
                                                             'ck_pack_context_key': 'length(trim(pack_key)) '
                                                                                    'BETWEEN 1 AND 64',
                                                             'ck_pack_context_revision': 'revision > 0',
                                                             'ck_pack_context_state': 'state IN '
                                                                                      "('draft','active','suspended','retired')",
                                                             'ck_pack_context_version': 'pack_version > 0'},
                                                  'columns': {'activation_id': ('INTEGER', False),
                                                              'branch_id': ('INTEGER', False),
                                                              'company_id': ('INTEGER', False),
                                                              'created_at': ('DATETIME', False),
                                                              'ever_activated': ('BOOLEAN', False),
                                                              'id': ('INTEGER', False),
                                                              'pack_key': ('VARCHAR(64)', False),
                                                              'pack_version': ('INTEGER', False),
                                                              'revision': ('INTEGER', False),
                                                              'state': ('VARCHAR(20)', False),
                                                              'updated_at': ('DATETIME', False)},
                                                  'foreign_keys': [(('company_id',),
                                                                    'companies',
                                                                    ('id',),
                                                                    'RESTRICT',
                                                                    False,
                                                                    False),
                                                                   (('branch_id',),
                                                                    'branches',
                                                                    ('id',),
                                                                    'RESTRICT',
                                                                    False,
                                                                    False),
                                                                   (('activation_id',
                                                                     'company_id',
                                                                     'pack_key',
                                                                     'pack_version'),
                                                                    'business_pack_activations',
                                                                    ('id',
                                                                     'company_id',
                                                                     'pack_key',
                                                                     'pack_version'),
                                                                    'RESTRICT',
                                                                    False,
                                                                    False)],
                                                  'pk': ('id',),
                                                  'unique': [('id', 'company_id', 'branch_id'),
                                                             ('activation_id', 'branch_id')]},
                       'business_pack_delivery_sources': {'checks': {'ck_pack_delivery_payload': 'length(payload_sha256)=64 '
                                                                                                 'AND '
                                                                                                 'length(source_key)>0',
                                                                     'ck_pack_delivery_scope': 'company_id > 0 '
                                                                                               'AND branch_id > 0 '
                                                                                               'AND context_id > '
                                                                                               '0 AND '
                                                                                               'pack_version > 0 '
                                                                                               'AND actor_user_id '
                                                                                               '> 0',
                                                                     'ck_pack_delivery_target': '(email_outbox_id '
                                                                                                'IS NOT NULL AND '
                                                                                                'notification_id '
                                                                                                'IS NULL) OR '
                                                                                                '(email_outbox_id '
                                                                                                'IS NULL AND '
                                                                                                'notification_id '
                                                                                                'IS NOT NULL)'},
                                                          'columns': {'actor_user_id': ('INTEGER', False),
                                                                      'branch_id': ('INTEGER', False),
                                                                      'company_id': ('INTEGER', False),
                                                                      'context_id': ('INTEGER', False),
                                                                      'created_at': ('DATETIME', False),
                                                                      'email_outbox_id': ('INTEGER', True),
                                                                      'id': ('INTEGER', False),
                                                                      'module': ('VARCHAR(60)', False),
                                                                      'notification_id': ('INTEGER', True),
                                                                      'pack_key': ('VARCHAR(60)', False),
                                                                      'pack_version': ('INTEGER', False),
                                                                      'payload_sha256': ('VARCHAR(64)', False),
                                                                      'recipient_email': ('VARCHAR(254)', True),
                                                                      'recipient_user_id': ('INTEGER', True),
                                                                      'source_key': ('VARCHAR(500)', False),
                                                                      'source_kind': ('VARCHAR(40)', False),
                                                                      'source_table': ('VARCHAR(120)', False)},
                                                          'foreign_keys': [(('email_outbox_id',),
                                                                            'email_outbox',
                                                                            ('id',),
                                                                            'RESTRICT',
                                                                            False,
                                                                            False),
                                                                           (('actor_user_id',),
                                                                            'users',
                                                                            ('id',),
                                                                            'RESTRICT',
                                                                            False,
                                                                            False),
                                                                           (('context_id',
                                                                             'company_id',
                                                                             'branch_id'),
                                                                            'business_pack_contexts',
                                                                            ('id', 'company_id', 'branch_id'),
                                                                            'RESTRICT',
                                                                            False,
                                                                            False),
                                                                           (('notification_id',),
                                                                            'notifications',
                                                                            ('id',),
                                                                            'RESTRICT',
                                                                            False,
                                                                            False),
                                                                           (('recipient_user_id',),
                                                                            'users',
                                                                            ('id',),
                                                                            'RESTRICT',
                                                                            False,
                                                                            False)],
                                                          'pk': ('id',),
                                                          'unique': [('email_outbox_id',), ('notification_id',)]},
                       'business_pack_master_availability': {'checks': {'ck_pack_master_active': 'active IN (0, '
                                                                                                 '1)',
                                                                        'ck_pack_master_key': 'length(trim(resource_key)) '
                                                                                              'BETWEEN 1 AND 500',
                                                                        'ck_pack_master_revision': 'revision > 0',
                                                                        'ck_pack_master_table': 'length(trim(resource_table)) '
                                                                                                'BETWEEN 1 AND '
                                                                                                '120'},
                                                             'columns': {'active': ('BOOLEAN', False),
                                                                         'branch_id': ('INTEGER', False),
                                                                         'company_id': ('INTEGER', False),
                                                                         'context_id': ('INTEGER', False),
                                                                         'created_at': ('DATETIME', False),
                                                                         'id': ('INTEGER', False),
                                                                         'resource_key': ('VARCHAR(500)', False),
                                                                         'resource_table': ('VARCHAR(120)', False),
                                                                         'revision': ('INTEGER', False),
                                                                         'updated_at': ('DATETIME', False)},
                                                             'foreign_keys': [(('branch_id',),
                                                                               'branches',
                                                                               ('id',),
                                                                               'RESTRICT',
                                                                               False,
                                                                               False),
                                                                              (('context_id',
                                                                                'company_id',
                                                                                'branch_id'),
                                                                               'business_pack_contexts',
                                                                               ('id', 'company_id', 'branch_id'),
                                                                               'RESTRICT',
                                                                               False,
                                                                               False),
                                                                              (('company_id',),
                                                                               'companies',
                                                                               ('id',),
                                                                               'RESTRICT',
                                                                               False,
                                                                               False)],
                                                             'pk': ('id',),
                                                             'unique': [('context_id',
                                                                         'resource_table',
                                                                         'resource_key')]},
                       'business_pack_record_ownership': {'checks': {'ck_pack_record_key': 'length(trim(resource_key)) '
                                                                                           'BETWEEN 1 AND 500',
                                                                     'ck_pack_record_revision': 'revision > 0',
                                                                     'ck_pack_record_source': 'length(trim(source)) '
                                                                                              'BETWEEN 1 AND 80',
                                                                     'ck_pack_record_table': 'length(trim(resource_table)) '
                                                                                             'BETWEEN 1 AND 120'},
                                                          'columns': {'branch_id': ('INTEGER', False),
                                                                      'company_id': ('INTEGER', False),
                                                                      'context_id': ('INTEGER', False),
                                                                      'created_at': ('DATETIME', False),
                                                                      'id': ('INTEGER', False),
                                                                      'resource_key': ('VARCHAR(500)', False),
                                                                      'resource_table': ('VARCHAR(120)', False),
                                                                      'revision': ('INTEGER', False),
                                                                      'source': ('VARCHAR(80)', False)},
                                                          'foreign_keys': [(('company_id',),
                                                                            'companies',
                                                                            ('id',),
                                                                            'RESTRICT',
                                                                            False,
                                                                            False),
                                                                           (('branch_id',),
                                                                            'branches',
                                                                            ('id',),
                                                                            'RESTRICT',
                                                                            False,
                                                                            False),
                                                                           (('context_id',
                                                                             'company_id',
                                                                             'branch_id'),
                                                                            'business_pack_contexts',
                                                                            ('id', 'company_id', 'branch_id'),
                                                                            'RESTRICT',
                                                                            False,
                                                                            False)],
                                                          'pk': ('id',),
                                                          'unique': [('resource_table', 'resource_key')]},
                       'business_pack_user_grants': {'checks': {'ck_pack_user_grant_active': 'active IN (0, 1)',
                                                                'ck_pack_user_grant_revision': 'revision > 0',
                                                                'ck_pack_user_grant_role': 'length(trim(role)) '
                                                                                           'BETWEEN 1 AND 64'},
                                                     'columns': {'active': ('BOOLEAN', False),
                                                                 'branch_id': ('INTEGER', False),
                                                                 'company_id': ('INTEGER', False),
                                                                 'context_id': ('INTEGER', False),
                                                                 'created_at': ('DATETIME', False),
                                                                 'id': ('INTEGER', False),
                                                                 'revision': ('INTEGER', False),
                                                                 'role': ('VARCHAR(64)', False),
                                                                 'updated_at': ('DATETIME', False),
                                                                 'user_id': ('INTEGER', False)},
                                                     'foreign_keys': [(('user_id',),
                                                                       'users',
                                                                       ('id',),
                                                                       'RESTRICT',
                                                                       False,
                                                                       False),
                                                                      (('company_id',),
                                                                       'companies',
                                                                       ('id',),
                                                                       'RESTRICT',
                                                                       False,
                                                                       False),
                                                                      (('context_id', 'company_id', 'branch_id'),
                                                                       'business_pack_contexts',
                                                                       ('id', 'company_id', 'branch_id'),
                                                                       'RESTRICT',
                                                                       False,
                                                                       False),
                                                                      (('branch_id',),
                                                                       'branches',
                                                                       ('id',),
                                                                       'RESTRICT',
                                                                       False,
                                                                       False)],
                                                     'pk': ('id',),
                                                     'unique': [('context_id', 'user_id')]},
                       'email_outbox': {'checks': {},
                                        'columns': {'accepted_at': ('DATETIME', True),
                                                    'attempts': ('INTEGER', False),
                                                    'body': ('TEXT', False),
                                                    'created_at': ('DATETIME', True),
                                                    'error': ('VARCHAR(240)', True),
                                                    'event_key': ('VARCHAR(180)', False),
                                                    'id': ('INTEGER', False),
                                                    'is_html': ('BOOLEAN', False),
                                                    'module': ('VARCHAR(60)', False),
                                                    'organization_id': ('INTEGER', True),
                                                    'provider_message_id': ('VARCHAR(200)', True),
                                                    'recipient': ('VARCHAR(254)', False),
                                                    'recipient_user_id': ('INTEGER', True),
                                                    'status': ('VARCHAR(30)', False),
                                                    'subject': ('VARCHAR(240)', False)},
                                        'foreign_keys': [],
                                        'pk': ('id',),
                                        'unique': [('event_key',)]},
                       'notifications': {'checks': {},
                                         'columns': {'action_url': ('VARCHAR(500)', True),
                                                     'channels': ('JSON', True),
                                                     'company_id': ('INTEGER', True),
                                                     'created_at': ('DATETIME', True),
                                                     'event_type': ('VARCHAR(80)', True),
                                                     'id': ('INTEGER', False),
                                                     'is_read': ('BOOLEAN', True),
                                                     'message': ('TEXT', False),
                                                     'module': ('VARCHAR(50)', True),
                                                     'priority': ('VARCHAR(20)', True),
                                                     'read_at': ('DATETIME', True),
                                                     'related_entity_id': ('INTEGER', True),
                                                     'related_entity_type': ('VARCHAR(80)', True),
                                                     'title': ('VARCHAR(200)', False),
                                                     'user_id': ('INTEGER', False)},
                                         'foreign_keys': [(('company_id',),
                                                           'companies',
                                                           ('id',),
                                                           'SET NULL',
                                                           False,
                                                           False),
                                                          (('user_id',),
                                                           'users',
                                                           ('id',),
                                                           'CASCADE',
                                                           False,
                                                           False)],
                                         'pk': ('id',),
                                         'unique': []}}}}
