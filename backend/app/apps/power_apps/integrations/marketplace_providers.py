"""Documented marketplace API operations using the shared transport and vault."""
import re
from fastapi import HTTPException

DYNAMIC = {
    'mailchimp': r'us[1-9][0-9]*\.api\.mailchimp\.com',
    'zendesk': r'[a-z0-9][a-z0-9-]*\.zendesk\.com',
    'activecampaign': r'[a-z0-9][a-z0-9-]*\.api-us1\.com',
    'docusign': r'account(?:-d)?\.docusign\.com',
}


def validate_host(key, config):
    host = config.get('provider_host', '')
    if not isinstance(host, str) or len(host)>253 or not re.fullmatch(DYNAMIC[key], host):
        raise HTTPException(422, 'Enter the exact supported provider hostname without a scheme, path or port')
    return host


def install(profile, a):
    profile('facebook_lead_ads','Facebook Lead Ads','CRM','graph.facebook.com',
        'https://developers.facebook.com/docs/marketing-api/guides/lead-ads/retrieving/',[
        a('test','Verify token identity','GET','/v24.0/me',query={'fields':'id,name'}),
        a('list_forms','Read Page lead forms','GET','/v24.0/{page_id}/leadgen_forms','page_id',query={'limit':25}),
        a('list_leads','Read form leads','GET','/v24.0/{form_id}/leads','form_id',query={'limit':25}),
    ])
    profile('mailchimp','Mailchimp','Email','us1.api.mailchimp.com',
        'https://mailchimp.com/developer/marketing/guides/quick-start/',[
        a('test','Verify Mailchimp API key','GET','/3.0/ping'),
        a('list_audiences','Read audiences','GET','/3.0/lists',query={'count':25}),
        a('list_members','Read audience contacts','GET','/3.0/lists/{list_id}/members','list_id',query={'count':25}),
    ],auth='basic')
    profile('docusign','DocuSign','Productivity','account-d.docusign.com',
        'https://developers.docusign.com/platform/auth/public-authcode-get-token',[
        a('test','Verify signing account access','GET','/oauth/userinfo'),
    ])
    profile('trello','Trello','Project Management','api.trello.com',
        'https://developer.atlassian.com/cloud/trello/guides/rest-api/authorization/',[
        a('test','Verify Trello member','GET','/1/members/me',query={'fields':'id,fullName,username'}),
        a('list_boards','Read member boards','GET','/1/members/me/boards',query={'fields':'id,name,closed'}),
        a('list_cards','Read board cards','GET','/1/boards/{board_id}/cards','board_id',query={'fields':'id,name,idList,closed'}),
    ],auth='basic')
    profile('zendesk','Zendesk','CRM','example.zendesk.com',
        'https://developer.zendesk.com/api-reference/introduction/security-and-auth/',[
        a('test','Verify Zendesk user','GET','/api/v2/users/me.json'),
        a('list_tickets','Read tickets','GET','/api/v2/tickets.json',query={'per_page':25}),
    ])
    profile('activecampaign','ActiveCampaign','Email','example.api-us1.com',
        'https://developers.activecampaign.com/reference/authentication',[
        a('test','Verify ActiveCampaign user','GET','/api/3/users/me'),
        a('list_contacts','Read contacts','GET','/api/3/contacts',query={'limit':25}),
        a('list_lists','Read contact lists','GET','/api/3/lists',query={'limit':25}),
    ],headers={'credential_header':'Api-Token'})
    profile('linkedin_lead_forms','LinkedIn Lead Forms','CRM','api.linkedin.com',
        'https://learn.microsoft.com/en-us/linkedin/marketing/lead-sync/leadsync?view=li-lms-2026-04',[
        a('test','Verify lead form access','GET','/rest/leadForms/{form_id}','form_id'),
        a('get_form','Read lead form','GET','/rest/leadForms/{form_id}','form_id'),
        a('list_responses','Read lead responses','GET','/rest/leadFormResponses','owner lead_type',
          query={'q':'owner','owner':'{owner}','leadType':'(leadType:{lead_type})','count':25}),
    ],headers={'LinkedIn-Version':'202610','X-Restli-Protocol-Version':'2.0.0'})
    profile('klaviyo','Klaviyo','Email','a.klaviyo.com',
        'https://developers.klaviyo.com/en/reference/get_accounts',[
        a('test','Verify Klaviyo account','GET','/api/accounts'),
        a('list_profiles','Read profiles','GET','/api/profiles',query={'page[size]':25}),
        a('list_lists','Read lists','GET','/api/lists',query={'page[size]':25}),
    ],headers={'revision':'2026-10-15'},prefix='Klaviyo-API-Key')
    profile('surfe','Surfe','CRM','api.surfe.com',
        'https://developers.surfe.com/public-017-get-credits',[
        a('test','Verify Surfe credits','GET','/v1/credits'),
    ])
    profile('apollo','Apollo.io','CRM','api.apollo.io',
        'https://docs.apollo.io/reference/authentication',[
        a('test','Verify Apollo API key','GET','/api/v1/auth/health'),
        a('list_users','Read account users (master key)','GET','/api/v1/users/search'),
    ],headers={'credential_header':'x-api-key'})
    profile('cloudtalk','CloudTalk','Communication','my.cloudtalk.io',
        'https://help.cloudtalk.io/developers',[
        a('test','Verify CloudTalk contact access','GET','/api/contacts/index.json',query={'limit':1}),
        a('list_contacts','Read contacts','GET','/api/contacts/index.json',query={'limit':25}),
        a('list_calls','Read call history','GET','/api/calls/index.json',query={'limit':25}),
    ],auth='basic',headers={'User-Agent':'BusinessSuite-Connector/1.0'})


SETUP = {
    'facebook_lead_ads': ['Use a Page access token authorized for leads_retrieval and Page lead access.', 'Meta app review and Page access are required. Verification does not grant permissions.'],
    'mailchimp': ['Use username anystring and your Mailchimp API key as the password.', 'Set provider hostname to the API key data centre, for example us21.api.mailchimp.com.'],
    'docusign': ['Use an eSignature OAuth access token with signature scope.', 'Choose account-d.docusign.com for demo or account.docusign.com for production. This adapter verifies account access; it does not send contracts.'],
    'trello': ['Enter the Trello application API key and an authorized user token.', 'Read-only member, board and card access is sufficient. Tokens are sent in the OAuth Authorization header.'],
    'zendesk': ['Use a Zendesk OAuth access token with read scope.', 'Set the exact company subdomain, for example acme.zendesk.com.'],
    'activecampaign': ['Use the API token from Settings > Developer.', 'Set your account API hostname, for example acme.api-us1.com.'],
    'linkedin_lead_forms': ['Use an OAuth token from an approved Lead Sync API application with r_marketing_leadgen_automation.', 'Set a lead form ID for verification. Lead response owner is Rest.li syntax, for example (sponsoredAccount:urn:li:sponsoredAccount:123). Lead type is SPONSORED, EVENT, COMPANY or ORGANIZATION_PRODUCT.'],
    'klaviyo': ['Use a private API key with accounts:read for verification and profiles:read or lists:read for those operations.'],
    'surfe': ['Use a Surfe API key. Verification reads credit balances and does not spend enrichment credits.'],
    'apollo': ['Use your Apollo API key. Reading account users additionally requires a master key.'],
    'cloudtalk': ['Enter your CloudTalk API Access Key ID and Access Key Secret as the basic credentials.'],
}
