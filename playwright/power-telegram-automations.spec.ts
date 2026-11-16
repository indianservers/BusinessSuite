import { test, expect } from '../frontend/node_modules/playwright/test';
import { setupPowerApps } from './power-apps-fixtures';
import { emptyExperience } from '../frontend/src/apps/power-apps/applications/automations/telegramExperienceTypes';

for (const width of [1440, 390]) {
  test(`Telegram auto-reply stays inside Automations at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await setupPowerApps(page, { configure: true });
    let enabled = true;
    let connected = false;
    let handoffStatus = 'waiting';
    let assigned = false;
    let stageApproved = false;
    let serviceStage = 'received';
    let employeeLinked = false;
    let botConfiguration = { audience: 'public', public_enabled: true, company_enabled: false, create_crm_records: false, company_user_ids: [], public_welcome: 'Welcome customers', company_welcome: 'Welcome employees' };
    let experience = structuredClone(emptyExperience);
    const transcript = [{ id: 1, direction: 'incoming', text: 'Please help with my order' }];
    await page.route('**/power-apps/automations/telegram/**', async route => {
      const path = new URL(route.request().url()).pathname;
      if (path.endsWith('/setup')) {
        expect(route.request().postDataJSON().token).toBe('123456789:fixture_only');
        expect(route.request().postDataJSON().audience).toBe('public');
        connected = true;
        return route.fulfill({ status: 201, json: { resource_id: 91, enabled: true, username: 'fixture_bot' } });
      }
      if (path.endsWith('/ai-configuration')) {
        const configuration = route.request().method() === 'PUT' ? route.request().postDataJSON() : { enabled: true, provider: 'local', public_context: '' };
        return route.fulfill({ json: { configuration, engine: 'actionbot', local_model: { active: true, engine: 'tensorflow-local-intents-v1', description: 'Fixture trained local model' } } });
      }
      if (path.endsWith('/employee-options')) return route.fulfill({ json: { items: [{ id: 3, employee_code: 'EMP-3', name: 'Alex Employee', user_id: 1 }] } });
      if (path.endsWith('/experience-options')) return route.fulfill({ json: { owner_user_id: 1, branch_id: 1, employees: [{ id: 3, employee_code: 'EMP-3', name: 'Alex Employee', user_id: 1 }], services: [{ id: 4, name: 'Consultation' }], resources: [{ id: 5, name: 'Dr Alex', type: 'provider' }] } });
      if (path.endsWith('/experience')) {
        if (route.request().method() === 'PUT') {
          experience = { ...route.request().postDataJSON(), revision: experience.revision + 1 };
          expect(experience.knowledge[0].source_reference).toBe('Hours policy v1');
          expect(experience.workflows[0].questions).toHaveLength(6);
          expect(experience.routing_agents[0].user_id).toBe(1);
          expect(experience.booking_services[0].resource_ids).toEqual([5]);
        }
        return route.fulfill({ json: { configuration: experience } });
      }
      if (path.endsWith('/employee-links')) { expect(route.request().postDataJSON()).toEqual({ employee_id: 3, telegram_user_id: '123456789' }); employeeLinked = true; return route.fulfill({ status: 201, json: { identity_id: 1 } }); }
      if (path.endsWith('/operations')) return route.fulfill({ json: { current_user_id: 1, can_manage: true, stage_reviews: stageApproved ? [] : [{ id: 81, operation: { conversation_id: 8, target: 'received' }, can_review: true, expires_at: new Date(Date.now() + 600000).toISOString() }], identities: employeeLinked ? [{ id: 1, interface: 'company', name: 'Alex Employee', telegram_user_id: '123456789', employee_id: 3, user_id: 1, verified: true }] : [], conversations: [{ id: 8, interface: 'public', chat_id: '42', status: handoffStatus, assignee_user_id: assigned ? 1 : null, context: { service_stage: serviceStage, stage_approved: stageApproved, stage_revision: stageApproved ? 1 : 0 }, service_stages: [{ key: 'received', label: 'Received', requires_approval: true, next_stages: ['completed'] }, { key: 'completed', label: 'Completed', requires_approval: false, next_stages: [] }], messages: transcript }] } });
      if (path.endsWith('/stage-reviews/81')) { expect(route.request().postDataJSON()).toEqual({ approved: true }); stageApproved = true; return route.fulfill({ json: { status: 'approved' } }); }
      if (path.endsWith('/conversations/8/stage')) { expect(route.request().postDataJSON()).toEqual({ target: 'completed', expected_revision: 1 }); serviceStage = 'completed'; return route.fulfill({ json: { status: 'completed' } }); }
      if (path.endsWith('/conversations/8/draft')) return route.fulfill({ json: { id: 82, text: 'We are checking your order.', expires_at: new Date(Date.now() + 300000).toISOString(), sources: [{ id: 'hours', url: 'https://example.com/hours', reference: 'Hours policy v1' }], sent: false } });
      if (path.endsWith('/conversations/8')) { const action = route.request().postDataJSON().action; handoffStatus = action === 'claim' ? 'assigned' : action === 'resolve' ? 'resolved' : 'bot'; assigned = action === 'claim'; return route.fulfill({ json: { status: handoffStatus } }); }
      if (path.endsWith('/conversations/8/reply')) { expect(route.request().postDataJSON().text).toBe('We are checking your order.'); expect(route.request().postDataJSON().draft_id).toBe(82); transcript.push({ id: 2, direction: 'outgoing', text: route.request().postDataJSON().text }); return route.fulfill({ status: 202, json: { run_id: 99, status: 'queued' } }); }
      if (path.endsWith('/configuration')) { botConfiguration = route.request().postDataJSON(); return route.fulfill({ json: { configuration: botConfiguration } }); }
      if (path.endsWith('/link-code')) { expect(route.request().postDataJSON()).toEqual({ interface: 'public', customer_id: 7 }); return route.fulfill({ json: { command: '/link fixture_one_time' } }); }
      if (path.endsWith('/simulate')) return route.fulfill({ json: { sent: false, steps: [{ message: 'Sales', reply: 'What is your name?', stage: 'name' }] } });
      if (path.endsWith('/91')) { enabled = route.request().postDataJSON().enabled; return route.fulfill({ json: { enabled } }); }
      return route.fulfill({ json: { items: connected ? [{ resource_id: 91, name: 'Telegram customer enquiries', username: 'fixture_bot', enabled, can_manage: true, configuration: botConfiguration, messages: [] }] : [] } });
    });
    await page.goto('/power-apps/automations');
    const panel = page.getByRole('region', { name: 'Telegram automations' });
    await expect(panel).toBeVisible({ timeout: 45000 });
    await panel.getByRole('button', { name: 'Connect Telegram bot' }).click();
    await panel.getByLabel('Telegram bot token').fill('123456789:fixture_only');
    await panel.getByRole('button', { name: 'Verify bot & enable auto-reply' }).click();
    await expect(panel.getByRole('link', { name: '@fixture_bot' })).toBeVisible();
    await expect(panel.getByLabel('Telegram bot token')).toHaveCount(0);
    await panel.getByRole('button', { name: 'Pause replies' }).click();
    await expect(panel.getByRole('button', { name: 'Enable replies' })).toBeVisible();
    await panel.getByText('Try the enquiry scenario locally', { exact: true }).click();
    await panel.getByRole('button', { name: 'Run local preview' }).click();
    await expect(panel.getByRole('status')).toContainText('What is your name?');
    await panel.getByRole('link', { name: 'Open Telegram configuration page' }).click();
    await expect(page).toHaveURL(/automations\/telegram/);
    const configuration = page.getByRole('region', { name: 'Telegram automations' });
    await expect(configuration.getByRole('combobox', { name: 'Bot purpose', exact: true })).toHaveValue('public');
    await expect(configuration.getByLabel('Public welcome message')).toBeVisible();
    await expect(configuration.getByLabel('Company welcome message')).toHaveCount(0);
    await configuration.getByLabel('Create CRM leads and tasks from completed requests').check();
    await configuration.getByLabel('Public welcome message').fill('Welcome customers');
    await configuration.getByRole('button', { name: 'Save interface settings' }).click();
    await expect(configuration.getByText('Telegram configuration saved.')).toBeVisible();
    await configuration.getByText('Identity linking & human handoff', { exact: true }).click();
    await expect(configuration.getByRole('button', { name: 'Generate my company link code' })).toHaveCount(0);
    await expect(configuration.getByRole('button', { name: 'Link employee Telegram ID' })).toHaveCount(0);
    await configuration.getByLabel('CRM record type').selectOption('customer');
    await configuration.getByLabel('CRM record ID').fill('7');
    await configuration.getByRole('button', { name: 'Generate customer linking code' }).click();
    await expect(configuration.getByLabel('One-time Telegram command')).toHaveValue('/link fixture_one_time');
    await configuration.getByRole('button', { name: /public · Chat 42/ }).click();
    await configuration.getByRole('button', { name: 'Claim conversation' }).click();
    await configuration.getByRole('button', { name: 'Approve service stage', exact: true }).click();
    await configuration.getByRole('combobox', { name: 'Next service stage', exact: true }).selectOption('completed');
    await configuration.getByRole('button', { name: 'Move service stage', exact: true }).click();
    await expect(configuration.getByText('Service stage: Completed', { exact: true })).toBeVisible();
    await expect(configuration.getByLabel('Reply through Telegram')).toBeEnabled();
    await configuration.getByRole('button', { name: 'Draft a grounded reply', exact: true }).click();
    await expect(configuration.getByLabel('Reply through Telegram')).toHaveValue('We are checking your order.');
    expect(transcript).toHaveLength(1);
    await expect(configuration.getByRole('link', { name: 'Hours policy v1', exact: true })).toBeVisible();
    await configuration.getByRole('button', { name: 'Queue Telegram reply' }).click();
    await expect(configuration.getByText('Reply queued. Check its execution status for delivery.')).toBeVisible();
    await expect(configuration.getByText('We are checking your order.', { exact: true })).toBeVisible();
    await configuration.getByRole('button', { name: 'Return to bot', exact: true }).click();
    await expect(configuration.getByLabel('Reply through Telegram')).toBeDisabled();
    await configuration.getByText('ActionBot AI model', { exact: true }).click();
    await expect(configuration.getByText(/Fixture trained local model/)).toBeVisible();
    await configuration.getByRole('combobox', { name: 'ActionBot model source', exact: true }).selectOption('preferred');
    await configuration.getByRole('button', { name: 'Save ActionBot AI settings' }).click();
    await expect(configuration.getByText('ActionBot AI settings saved.')).toBeVisible();
    await configuration.getByText('Knowledge, industry workflows & service operations', { exact: true }).click();
    await configuration.getByRole('button', { name: 'Add knowledge item', exact: true }).click();
    await configuration.getByLabel('Knowledge title', { exact: true }).fill('Business hours');
    await configuration.getByLabel('Approved content', { exact: true }).fill('The showroom opens at 9 AM.');
    await configuration.getByLabel('Source URL', { exact: true }).fill('https://example.com/hours');
    await configuration.getByLabel('Source reference', { exact: true }).fill('Hours policy v1');
    await configuration.getByLabel('I verified this information and approve it for publication').check();
    await configuration.getByRole('tab', { name: 'Industry workflows', exact: true }).click();
    await configuration.getByRole('button', { name: 'Add qualification workflow' }).click();
    await expect(configuration.getByLabel('Workflow name', { exact: true })).toBeVisible();
    await configuration.getByRole('tab', { name: 'Routing & deadlines' }).click();
    await configuration.getByRole('button', { name: 'Add routing employee', exact: true }).click();
    await configuration.getByRole('combobox', { name: 'Routing employee', exact: true }).selectOption('1');
    await configuration.getByLabel('Staff skills', { exact: true }).fill('sales, support');
    await configuration.getByRole('tab', { name: 'Appointment services' }).click();
    await configuration.getByRole('button', { name: 'Add appointment service', exact: true }).click();
    await configuration.getByRole('combobox', { name: 'Appointment service', exact: true }).selectOption('4');
    await configuration.getByLabel('Dr Alex · provider', { exact: true }).check();
    await configuration.getByRole('button', { name: 'Publish Telegram experience (revision 1)' }).click();
    await expect(configuration.getByText('Telegram experience published.', { exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2)).toBeTruthy();
  });
}

for (const width of [1440, 390]) {
  test(`Dedicated company bot requires its own token and hides customer linking at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await setupPowerApps(page, { configure: true });
    let connected = false;
    let setupCalls = 0;
    let companyClaimed = false;
    const configuration = { audience: 'company', public_enabled: false, company_enabled: true, create_crm_records: false, company_user_ids: [], public_welcome: 'Customer greeting', company_welcome: 'Employee greeting' };
    await page.route('**/power-apps/automations/telegram/**', async route => {
      const path = new URL(route.request().url()).pathname;
      if (path.endsWith('/setup')) {
        setupCalls++;
        expect(route.request().postDataJSON()).toMatchObject({ audience: 'company', token: '987654321:separate_company_fixture' });
        connected = true;
        return route.fulfill({ status: 201, json: { resource_id: 92 } });
      }
      if (path.endsWith('/operations')) return route.fulfill({ json: { audience: 'company', current_user_id: 1, can_manage: true, identities: [], conversations: [{ id: 9, interface: 'company', chat_id: '77', status: companyClaimed ? 'assigned' : 'waiting', assignee_user_id: companyClaimed ? 1 : null, messages: [{ id: 1, direction: 'incoming', text: 'Please help with an internal request' }] }] } });
      if (path.endsWith('/conversations/9')) { expect(route.request().postDataJSON()).toEqual({ action: 'claim' }); companyClaimed = true; return route.fulfill({ json: { status: 'assigned' } }); }
      if (path.endsWith('/employee-options')) return route.fulfill({ json: { items: [{ id: 3, name: 'Alex Employee', employee_code: 'EMP-3', user_id: 1 }] } });
      if (path.endsWith('/link-code')) { expect(route.request().postDataJSON()).toEqual({ interface: 'company' }); return route.fulfill({ json: { command: '/link company_one_time' } }); }
      return route.fulfill({ json: { items: connected ? [{ resource_id: 92, name: 'Company employee workspace', username: 'company_fixture_bot', enabled: true, can_manage: true, configuration, messages: [] }] : [] } });
    });
    await page.goto('/power-apps/automations/telegram');
    const panel = page.getByRole('region', { name: 'Telegram automations' });
    await expect(panel).toBeVisible({ timeout: 45000 });
    await panel.getByRole('button', { name: 'Connect Telegram bot' }).click();
    await panel.getByLabel('New bot purpose').selectOption('company');
    await expect(panel.getByLabel('Telegram bot token')).toHaveAttribute('required', '');
    await panel.getByRole('button', { name: 'Verify bot & enable auto-reply' }).click();
    expect(setupCalls).toBe(0);
    await panel.getByLabel('Telegram bot token').fill('987654321:separate_company_fixture');
    await panel.getByRole('button', { name: 'Verify bot & enable auto-reply' }).click();
    await expect(panel.getByRole('link', { name: '@company_fixture_bot' })).toBeVisible();
    await expect(panel.getByLabel('Company welcome message')).toBeVisible();
    await expect(panel.getByLabel('Public welcome message')).toHaveCount(0);
    await panel.getByText('Identity linking & human handoff', { exact: true }).click();
    await expect(panel.getByRole('button', { name: 'Link employee Telegram ID' })).toBeVisible();
    await expect(panel.getByLabel('CRM record type')).toHaveCount(0);
    await expect(panel.getByRole('button', { name: 'Generate customer linking code' })).toHaveCount(0);
    await expect(panel.getByText('Conversation inbox', { exact: true })).toBeVisible();
    await panel.getByRole('button', { name: /company · Chat 77/ }).click();
    await panel.getByRole('button', { name: 'Claim conversation' }).click();
    await expect(panel.getByLabel('Reply through Telegram')).toBeEnabled();
    await panel.getByRole('button', { name: 'Generate my company link code' }).click();
    await expect(panel.getByLabel('One-time Telegram command')).toHaveValue('/link company_one_time');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2)).toBeTruthy();
  });

  test(`Legacy shared bot changes purpose only after explicit save at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await setupPowerApps(page, { configure: true });
    let saves = 0;
    let configuration = { audience: 'shared', public_enabled: true, company_enabled: true, create_crm_records: false, company_user_ids: [], public_welcome: 'Customer greeting', company_welcome: 'Employee greeting' };
    await page.route('**/power-apps/automations/telegram/**', async route => {
      const path = new URL(route.request().url()).pathname;
      if (path.endsWith('/configuration')) {
        saves++; configuration = route.request().postDataJSON();
        expect(configuration).toMatchObject({ audience: 'public', public_enabled: true, company_enabled: false });
        return route.fulfill({ json: { configuration } });
      }
      if (path.endsWith('/operations')) return route.fulfill({ json: { audience: configuration.audience, current_user_id: 1, can_manage: true,
        identities: [{ id: 1, interface: 'company', name: 'Private employee identity', telegram_user_id: '77', verified: true }, { id: 2, interface: 'public', name: 'Customer identity', telegram_user_id: '42', verified: true }],
        conversations: [{ id: 9, interface: 'company', chat_id: '77', status: 'assigned', assignee_user_id: 1, messages: [{ id: 1, direction: 'incoming', text: 'Confidential company conversation' }] },
          { id: 10, interface: 'public', chat_id: '42', status: 'assigned', assignee_user_id: 1, messages: [{ id: 2, direction: 'incoming', text: 'Public customer enquiry' }] }] } });
      if (path.endsWith('/conversations/9/draft')) return route.fulfill({ json: { id: 82, text: 'Confidential employee suggestion', expires_at: new Date(Date.now() + 300000).toISOString(), sources: [], sent: false } });
      if (path.endsWith('/employee-options')) return route.fulfill({ json: { items: [] } });
      return route.fulfill({ json: { items: [{ resource_id: 91, name: 'Existing bot', username: 'legacy_fixture_bot', enabled: true, can_manage: true, configuration, messages: [] }] } });
    });
    await page.goto('/power-apps/automations/telegram');
    const panel = page.getByRole('region', { name: 'Telegram automations' });
    await expect(panel.getByRole('combobox', { name: 'Bot purpose', exact: true })).toHaveValue('shared', { timeout: 45000 });
    await expect(panel.getByRole('combobox', { name: 'Bot purpose', exact: true }).locator('option[value="company"]')).toHaveCount(0);
    await panel.getByText('Identity linking & human handoff', { exact: true }).click();
    await expect(panel.getByRole('button', { name: 'Generate my company link code' })).toBeVisible();
    await expect(panel.getByLabel('CRM record type')).toBeVisible();
    await panel.getByRole('button', { name: /company · Chat 77/ }).click();
    await expect(panel.getByText('Confidential company conversation', { exact: true })).toBeVisible();
    await panel.getByRole('button', { name: 'Draft a grounded reply', exact: true }).click();
    await expect(panel.getByLabel('Reply through Telegram')).toHaveValue('Confidential employee suggestion');
    await panel.getByRole('combobox', { name: 'Bot purpose', exact: true }).selectOption('public');
    expect(saves).toBe(0);
    await expect(panel.getByText('Legacy shared bot · choose a dedicated purpose', { exact: true })).toBeVisible();
    await expect(panel.getByRole('button', { name: 'Generate my company link code' })).toBeVisible();
    const refreshedOperations = page.waitForRequest(request => new URL(request.url()).pathname.endsWith('/operations'), { timeout: 3000 });
    await panel.getByRole('button', { name: 'Save interface settings' }).click();
    await refreshedOperations;
    await expect(panel.getByText('Telegram configuration saved.', { exact: true })).toBeVisible();
    await expect(panel.getByRole('button', { name: 'Generate my company link code' })).toHaveCount(0);
    await expect(panel.getByLabel('Company welcome message')).toHaveCount(0);
    await expect(panel.getByText('Conversation inbox', { exact: true })).toBeVisible();
    await expect(panel.getByRole('button', { name: /company · Chat 77/ })).toHaveCount(0);
    await expect(panel.getByText('Confidential company conversation', { exact: true })).toHaveCount(0);
    await expect(panel.getByText(/Private employee identity/)).toHaveCount(0);
    await expect(panel.getByLabel('Reply through Telegram')).toHaveCount(0);
    await panel.getByRole('button', { name: /public · Chat 42/ }).click();
    await expect(panel.getByLabel('Reply through Telegram')).toHaveValue('');
    await expect(panel.getByText(/Suggestion expires/)).toHaveCount(0);
    expect(saves).toBe(1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2)).toBeTruthy();
  });
}
