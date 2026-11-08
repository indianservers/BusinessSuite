"""Shared discovery metadata; connection creation stays in the existing vault API."""

# One provider entry per underlying connector, even when the source offers several apps.
APPS = [
    ('google_calendar', 'Google Meet', 'Productivity', ['crm','pms','hrms','srm'], 'Schedule meetings through the existing Google Calendar connector.'),
    ('microsoft_teams', 'Microsoft Teams', 'Collaboration', ['crm','pms','hrms','srm'], 'Meetings and team communication.'),
    ('slack', 'Slack', 'Communication', ['crm','pms','hrms','srm','fam'], 'Team notifications and conversations; reuses the Slack connector.'),
    ('facebook_lead_ads', 'Facebook Lead Ads', 'CRM', ['crm'], 'Lead form acquisition.'),
    ('quickbooks', 'QuickBooks', 'Finance', ['fam','srm','crm'], 'Reuse the existing authorized accounting import and sync.'),
    ('zoom', 'Zoom Meetings', 'Collaboration', ['crm','pms','hrms','srm'], 'Verify an authorized Zoom user and read meetings.'),
    ('mailchimp', 'Mailchimp', 'Email', ['crm','srm'], 'Sync audience contacts through one authorized Mailchimp connection.'),
    ('docusign', 'DocuSign', 'Productivity', ['crm','srm','hrms'], 'Sync envelopes and create native-contact contract drafts.'),
    ('asana', 'Asana', 'Project Management', ['pms','crm'], 'Reuse the existing Asana task connector.'),
    ('trello', 'Trello', 'Project Management', ['pms','crm'], 'Boards and task coordination.'),
    ('zendesk', 'Zendesk', 'CRM', ['crm','srm'], 'Customer service tickets.'),
    ('activecampaign', 'ActiveCampaign', 'Email', ['crm','srm'], 'Sync contacts with an authorized account API token.'),
    ('linkedin_lead_forms', 'LinkedIn Lead Forms', 'CRM', ['crm'], 'Lead form acquisition.'),
    ('monday', 'monday.com', 'Project Management', ['pms','crm'], 'Reuse the existing monday.com connector.'),
    ('calendly', 'Calendly', 'Productivity', ['crm','pms','hrms','srm'], 'Verify an authorized Calendly account.'),
    ('brevo', 'Brevo', 'Email', ['crm','srm'], 'Reuse the existing Brevo connector.'),
    ('klaviyo', 'Klaviyo', 'Email', ['crm','srm'], 'Sync profiles using OAuth or a scoped private API key.'),
    ('whatsapp_business', 'WhatsApp Business', 'Communication', ['crm','srm','hrms'], 'Reuse the existing WhatsApp Business connector.'),
    ('zapier', 'Zapier', 'Webhooks and APIs', ['crm','pms','hrms','srm','fam'], 'Use the existing signed webhook and HTTP adapters.'),
    ('pandadoc', 'PandaDoc', 'Productivity', ['crm','srm','hrms'], 'Read documents with an authorized API key.'),
    ('surfe', 'Surfe', 'CRM', ['crm'], 'Enrich native CRM contacts and import results with explicit credit approval.'),
    ('dedupely', 'Dedupely', 'CRM', ['crm'], 'Duplicate management integration.'),
    ('nova', 'Pipedrive Nova', 'AI Services', ['crm'], 'Pipedrive-specific product; no standalone ERP authorization is claimed.'),
    ('apollo', 'Apollo.io', 'CRM', ['crm'], 'Prospecting and contact enrichment.'),
    ('cloudtalk', 'CloudTalk', 'Communication', ['crm','srm'], 'Import contacts and call history; create contacts from native CRM records.'),
]


def discovery():
    from app.apps.power_apps.integrations.registry import catalog
    existing = {item['id']: item for item in catalog()}
    items = []
    for key, name, category, modules, description in APPS:
        adapter = existing.get(key)
        external = key == 'quickbooks'
        target = '/fam/import-data' if external else '/power-apps/integrations?connector=' + key
        if key == 'zapier':
            target = '/power-apps/integrations?connector=outgoing_webhook'
        items.append(dict(id=key, name=name, category=category, modules=modules,
            description=description, implemented=bool(adapter) or external or key=='zapier',
            authorization=adapter['authentication'] if adapter else ['provider_account'] if external else ['signed_webhook'] if key=='zapier' else [],
            destination=target if adapter or external or key=='zapier' else None,
            actions=[a['name'] for a in adapter['actions']] if adapter else [],
            setup=adapter['setup'] if adapter else ['Use the existing accounting authorization and sync workspace.'] if external else ['Provider adapter and authorization setup are not implemented yet.'],
            documentation_url=adapter['documentation_url'] if adapter else None))
        if key in {'dedupely','nova'}:
            items[-1]['blocked_reason'] = ('External API and authorization contract unavailable; no partner developer account was supplied. ' +
                ('Nova is documented as a built-in Pipedrive feature.' if key=='nova' else 'Dedupely developer API link redirects to its product page.'))
            items[-1]['documentation_url'] = 'https://support.pipedrive.com/en/article/nova-meetings' if key=='nova' else 'https://dedupe.ly/product'
            items[-1]['setup'] = [items[-1]['blocked_reason'], 'An adapter requires documented provider endpoints and authorized access; no connection is created.']
    covered = {item['id'] for item in items}
    category_modules = {'Finance':['fam','srm'], 'Payments':['fam','srm'], 'CRM':['crm'],
        'Project Management':['pms','crm'], 'HR':['hrms'], 'Email':['crm','srm','hrms'],
        'Communication':['crm','pms','hrms','srm','fam']}
    for key, adapter in existing.items():
        if key in covered:
            continue
        items.append(dict(id=key, name=adapter['name'], category=adapter['category'],
            modules=category_modules.get(adapter['category'], ['crm','pms','hrms','srm','fam']),
            description=adapter['description'], implemented=True, authorization=adapter['authentication'],
            destination='/power-apps/integrations?connector='+key,
            actions=[a['name'] for a in adapter['actions']], setup=adapter['setup'],
            documentation_url=adapter['documentation_url']))
    return items
