const path = require('node:path');
const { chromium, expect: base } = require('playwright/test');
const expect = base.configure({ timeout: 20000 });

(async () => {
  process.chdir(path.resolve(__dirname, '..'));
  const { createServer } = await import('vite');
  const server = await createServer({ root: process.cwd(), server: { host: '127.0.0.1', port: 0, hmr: false, watch: null } });
  await server.listen();
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({ viewport: { width: 390, height: 900 } });
    const errors = [], writes = [], reads = [];
    let fail = false, failCurriculum = false, deny = false, hold = false, release;
    let curriculum = { revision: 1, sections: [
      { id: 's1', title: 'First section', lessons: [{ id: 'l1', title: 'Original lesson', content: 'Full lesson content' }] },
      { id: 's2', title: 'Second section', lessons: [] },
    ] };
    const courses = [{ id: 1, code: 'SAFE-101', title: 'Safety essentials', category: 'Compliance', delivery_mode: 'Online', duration_hours: '2.5', content_standard: 'SCORM', external_launch_url: 'https://learning.example.test/' + 'full-course-details/'.repeat(7), scorm_version: '2004', xapi_activity_id: 'urn:original:activity', is_mandatory: true }];
    const assignments = Array.from({ length: 8 }, (_, i) => ({ id: i + 1, course_id: 1, employee_id: i + 1, status: i === 0 ? 'Completed' : 'Assigned', due_date: '2026-12-01' }));
    page.on('pageerror', error => errors.push(error.message));
    await page.route('**/api/v1/**', async route => {
      const request = route.request(), p = new URL(request.url()).pathname;
      let data = [];
      if (request.method() !== 'GET') {
        const body = request.postDataJSON();
        writes.push({ p, body });
        if (hold) await new Promise(resolve => release = resolve);
        if (deny) { await route.fulfill({ status: 403, json: { detail: 'Denied' } }); return; }
        if (p.endsWith('/curriculum')) {
          expect(body.revision).toBe(curriculum.revision);
          curriculum = { revision: curriculum.revision + 1, sections: body.sections };
          data = curriculum;
        } else if (p.endsWith('/courses')) {
          data = { id: 20, ...body }; courses.push(data);
        }
      } else {
        reads.push(p);
        if (fail || failCurriculum && p.endsWith('/curriculum')) { await route.fulfill({ status: 503, json: { detail: 'Unavailable' } }); return; }
        if (p.endsWith('/courses')) data = page.url().includes('drafts') ? [...courses, {...courses[0],id:2,title:'Leadership essentials'}] : courses;
        else if (p.endsWith('/assignments')) data = assignments;
        else if (p.endsWith('/curriculum')) data = p.includes('/courses/2/') ? {revision:1,sections:[{id:'s9',title:'Leadership section',lessons:[]}]} : curriculum;
      }
      await route.fulfill({ json: data });
    });
    await page.route('**/lms-mobile-qa*', route => route.fulfill({ contentType: 'text/html', body: '<meta name="viewport" content="width=device-width,initial-scale=1"><div id="root"></div><script type="module">import R from "/@react-refresh";R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;await import("/scripts/fixtures/mobile-lms.tsx");</script>' }));
    const origin = 'http://127.0.0.1:' + server.httpServer.address().port;
    const go = async (search = '?seed') => {
      await page.goto(origin + '/lms-mobile-qa' + search, { waitUntil: 'domcontentloaded', timeout: 90000 });
      await expect(page.getByRole('heading', { name: 'Learning Management', exact: true })).toBeVisible();
    };
    const open = async () => { await page.getByRole('button', { name: 'New Course', exact: true }).click(); return page.getByRole('dialog', { name: 'Publish Course', exact: true }); };
    const image = name => page.screenshot({ animations: 'disabled', path: path.resolve(__dirname, '../../outputs/mobile-ux/' + name + '.png') });
    const openCurriculum = async () => {
      await page.locator('summary').filter({ hasText: 'Arrange course sections and lessons' }).click();
      await page.locator('summary').filter({ hasText: /^Safety essentials$/ }).click();
    };
    if (process.env.MOBILE_LMS_BASELINE) {
      await go(); await expect(page.getByText('Employee #5', { exact: true })).toBeVisible();
      await image('lms-before-390'); await open(); await image('lms-create-before-390');
      console.log('Captured original LMS phone baseline.'); return;
    }

    for (const width of [320, 360, 375, 390, 414, 430, 480]) {
      await page.setViewportSize({ width, height: 900 }); await go();
      await expect(page.getByText('Employee #8', { exact: true })).toBeVisible();
      await expect(page.getByText('Certificate 8', { exact: true })).toBeVisible();
      await expect(page.getByText('Certification #108', { exact: true })).toBeVisible();
      await expect(page.getByText(courses[0].external_launch_url, { exact: true })).toBeVisible();
      await expect(page.locator('.hrms-lms-kpis .kf-card')).toHaveCount(5);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      const dialog = await open();
      for (const name of ['Course code', 'Course title', 'Course category', 'Course delivery', 'Course hours', 'Course standard']) {
        const input = dialog.getByLabel(name, { exact: true });
        await expect(input).toBeVisible();
        expect(await input.evaluate(e => parseFloat(getComputedStyle(e).fontSize))).toBeGreaterThanOrEqual(16);
      }
      await dialog.locator('summary').filter({ hasText: 'External learning details' }).click();
      for (const name of ['External Launch URL', 'SCORM Version', 'xAPI Activity ID']) await expect(dialog.getByLabel(name, { exact: true })).toBeVisible();
      await expect(dialog).toContainText('Create a course that HR can assign by employee or role.');
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await dialog.press('Escape');
      await openCurriculum();
      for (const name of ['New course section', 'New lesson', 'Lesson section']) {
        const input = page.getByLabel(name, { exact: true }); await expect(input).toBeVisible();
        expect(await input.evaluate(e => parseFloat(getComputedStyle(e).fontSize))).toBeGreaterThanOrEqual(16);
      }
      await expect(page.getByRole('button', { name: 'Move First section down', exact: true })).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    }

    await page.setViewportSize({ width: 390, height: 900 }); await go('?seed&drafts');
    const draftsWrites = writes.length;
    await openCurriculum();
    await page.getByLabel('New course section',{exact:true}).fill('Unfinished section');
    await page.getByLabel('New lesson',{exact:true}).fill('Unfinished lesson');
    await page.getByLabel('Lesson section',{exact:true}).selectOption('s2');
    await page.locator('summary').filter({hasText:/^Leadership essentials$/}).click();
    await expect(page.getByLabel('New course section',{exact:true})).toHaveValue('');
    await page.getByLabel('New course section',{exact:true}).fill('Leadership draft');
    await page.locator('summary').filter({hasText:/^Safety essentials$/}).click();
    await page.locator('summary').filter({hasText:/^Safety essentials$/}).click();
    await expect(page.getByLabel('New course section',{exact:true})).toHaveValue('Unfinished section');
    await expect(page.getByLabel('New lesson',{exact:true})).toHaveValue('Unfinished lesson');
    await expect(page.getByLabel('Lesson section',{exact:true})).toHaveValue('s2');
    const draftValues = async (section='Unfinished section',lesson='Unfinished lesson',target='s2') => {
      await expect(page.getByLabel('New course section',{exact:true})).toHaveValue(section);
      await expect(page.getByLabel('New lesson',{exact:true})).toHaveValue(lesson);
      await expect(page.getByLabel('Lesson section',{exact:true})).toHaveValue(target);
    };
    const outline = page.locator('[data-card-collection="apps/hrms/pages/lms/LMSPage:cards-1"]');
    await outline.getByRole('tab',{name:'Table',exact:true}).click();
    await expect(page.getByLabel('New course section',{exact:true})).toHaveCount(0);
    await outline.getByRole('tab',{name:'Cards',exact:true}).click();
    await page.locator('summary').filter({hasText:/^Safety essentials$/}).click();
    await draftValues();
    await page.getByRole('link',{name:'Leave learning',exact:true}).click();
    await expect(page.getByRole('heading',{name:'Away from learning',exact:true})).toBeVisible();
    await page.getByRole('link',{name:'Return to learning',exact:true}).click();
    await openCurriculum(); await draftValues();
    await go('?seed&drafts'); await openCurriculum(); await draftValues();
    await page.evaluate(()=>window.__lmsQa.setActor(2));
    await expect(page.getByLabel('New course section',{exact:true})).toHaveValue('');
    await page.getByLabel('New course section',{exact:true}).fill('Another actor draft');
    await page.evaluate(()=>window.__lmsQa.setActor(1)); await draftValues();
    for(const context of ['suite-branch','suite-organization','suite-tenant']){
      await page.evaluate(name=>window.__lmsQa.setContext(name,'other-context'),context);
      await expect(page.getByLabel('New course section',{exact:true})).toHaveValue('');
      await page.getByLabel('New course section',{exact:true}).fill('Different '+context);
      await page.evaluate(name=>window.__lmsQa.setContext(name,''),context); await draftValues();
    }
    await expect(page.getByRole('status').filter({hasText:'Draft kept for this browser tab.'})).toBeVisible();
    await image('lms-curriculum-draft-390');
    const fullCurriculum=structuredClone(curriculum);
    curriculum={...curriculum,sections:curriculum.sections.filter(s=>s.id!=='s2')};
    await go('?seed&drafts'); await openCurriculum();
    await expect(page.getByRole('alert').filter({hasText:'selected section is no longer available'})).toBeVisible();
    await expect(page.getByLabel('New lesson',{exact:true})).toHaveValue('Unfinished lesson');
    await expect(page.getByRole('button',{name:'Add lesson',exact:true})).toBeDisabled();
    await page.getByLabel('Lesson section',{exact:true}).selectOption('s1');
    await expect(page.getByRole('button',{name:'Add lesson',exact:true})).toBeEnabled();
    await page.getByRole('button',{name:'Discard curriculum draft',exact:true}).click();
    await expect(page.getByRole('alertdialog')).toContainText('Published curriculum stays unchanged.');
    await page.getByRole('button',{name:'Continue editing',exact:true}).click();
    await expect(page.getByLabel('New lesson',{exact:true})).toHaveValue('Unfinished lesson');
    await page.getByRole('button',{name:'Discard curriculum draft',exact:true}).click();
    await page.getByRole('button',{name:'Discard draft',exact:true}).click();
    await draftValues('','','s1');
    expect(writes.length).toBe(draftsWrites);
    curriculum=structuredClone(fullCurriculum);
    await go('?seed&drafts'); await openCurriculum();
    await page.getByLabel('New course section',{exact:true}).fill('Saved while away');
    await page.getByLabel('New lesson',{exact:true}).fill('Keep other draft');
    await page.getByLabel('Lesson section',{exact:true}).selectOption('s2');
    hold=true;release=undefined;
    await page.getByRole('button',{name:'Add section',exact:true}).click();
    for(const name of ['New course section','New lesson','Lesson section'])await expect(page.getByLabel(name,{exact:true})).toBeDisabled();
    await expect.poll(()=>typeof release).toBe('function');
    await page.getByRole('link',{name:'Leave learning',exact:true}).click();
    await expect(page.getByRole('heading',{name:'Away from learning',exact:true})).toBeVisible();
    await page.evaluate(()=>window.__lmsQa.setActor(2));const readsAtRelease=reads.length;release();hold=false;
    await expect.poll(()=>page.evaluate(()=>Object.keys(sessionStorage).filter(key=>key.includes('hrms-lms-curriculum:')).map(key=>JSON.parse(sessionStorage.getItem(key))).some(draft=>draft.section===''&&draft.lesson==='Keep other draft'))).toBe(true);
    expect(reads.length).toBe(readsAtRelease);
    await page.getByRole('link',{name:'Return to learning',exact:true}).click();await openCurriculum();
    await expect(page.getByLabel('New course section',{exact:true})).toHaveValue('Another actor draft');
    await expect(page.getByLabel('New lesson',{exact:true})).toHaveValue('');
    await page.evaluate(()=>window.__lmsQa.setActor(1));await draftValues('','Keep other draft','s2');
    expect(curriculum.sections.some(s=>s.title==='Saved while away')).toBe(true);
    await page.getByRole('button',{name:'Discard curriculum draft',exact:true}).click();
    await page.getByRole('button',{name:'Discard draft',exact:true}).click();
    curriculum=fullCurriculum;
    await go('?seed&drafts');await openCurriculum();
    await page.evaluate(()=>{window.__lmsSetItem=Storage.prototype.setItem;Storage.prototype.setItem=function(key,value){if(key.includes('hrms-lms-curriculum:'))throw new DOMException('Blocked','QuotaExceededError');return window.__lmsSetItem.call(this,key,value);};});
    await page.getByLabel('New course section',{exact:true}).fill('Storage unavailable draft');
    await expect(page.getByRole('alert').filter({hasText:'Draft could not be stored'})).toBeVisible();
    await expect(page.getByLabel('New course section',{exact:true})).toHaveValue('Storage unavailable draft');
    await page.evaluate(()=>{Storage.prototype.setItem=window.__lmsSetItem;});
    await page.getByLabel('New course section',{exact:true}).fill('');
    await go();
    let dialog = await open();
    await expect(dialog.getByLabel('Course category', { exact: true })).toHaveValue('Compliance');
    await expect(dialog.getByLabel('Course delivery', { exact: true })).toHaveValue('Online');
    await expect(dialog.getByLabel('Course hours', { exact: true })).toHaveValue('1');
    await expect(dialog.getByLabel('Course standard', { exact: true })).toHaveValue('Internal');
    await expect(dialog.locator('.smart-create-footer').getByRole('button', { name: 'Publish', exact: true })).toBeDisabled();
    await dialog.getByLabel('Course code', { exact: true }).fill('LEARN-20');
    await dialog.getByLabel('Course title', { exact: true }).fill('External safety course');
    await dialog.getByLabel('Course category', { exact: true }).fill('Safety');
    await dialog.getByLabel('Course delivery', { exact: true }).selectOption('Blended');
    await dialog.getByLabel('Course hours', { exact: true }).fill('2.75');
    await dialog.getByLabel('Course standard', { exact: true }).selectOption('xAPI');
    await dialog.locator('summary').filter({ hasText: 'External learning details' }).click();
    await dialog.getByLabel('External Launch URL', { exact: true }).fill('https://learning.example.test/course-20');
    await dialog.getByLabel('SCORM Version', { exact: true }).fill('2004');
    await dialog.getByLabel('xAPI Activity ID', { exact: true }).fill('urn:learning:20');
    await dialog.press('Escape'); await expect(page.getByRole('alertdialog')).toContainText('Discard changes?');
    await page.getByRole('button', { name: 'Continue Editing', exact: true }).click();
    deny = true; await dialog.locator('.smart-create-footer').getByRole('button', { name: 'Publish', exact: true }).click();
    await expect(dialog.getByRole('alert')).toContainText('Your course details are retained');
    await expect(dialog.getByLabel('Course title', { exact: true })).toHaveValue('External safety course');
    deny = false; hold = true; release = undefined;
    await dialog.locator('.smart-create-footer').getByRole('button', { name: 'Publish', exact: true }).click();
    await expect(dialog.locator('.smart-create-footer').getByRole('button', { name: 'Publish', exact: true })).toBeDisabled();
    await dialog.press('Escape'); await expect(dialog).toBeVisible();
    await expect.poll(() => typeof release).toBe('function'); release(); hold = false;
    await expect(dialog).toHaveCount(0);
    expect(writes.at(-1)).toEqual({ p: '/api/v1/lms/courses', body: { code: 'LEARN-20', title: 'External safety course', category: 'Safety', delivery_mode: 'Blended', duration_hours: 2.75, content_standard: 'xAPI', external_launch_url: 'https://learning.example.test/course-20', scorm_version: '2004', xapi_activity_id: 'urn:learning:20', is_mandatory: true } });
    dialog = await open(); await expect(dialog.getByLabel('Course code', { exact: true })).toHaveValue('');
    await image('lms-create-after-390'); await dialog.press('Escape');
    while (await page.locator('[data-state="open"] [toast-close]').count()) await page.locator('[data-state="open"] [toast-close]').first().click();
    await expect(page.locator('[toast-close]')).toHaveCount(0); await page.evaluate(() => scrollTo(0, 0)); await image('lms-after-390');

    await openCurriculum();
    await page.getByLabel('New course section', { exact: true }).fill(' Third section ');
    deny = true; await page.getByRole('button', { name: 'Add section', exact: true }).click();
    await expect(page.getByRole('alert').filter({ hasText: 'Could not save curriculum' })).toBeVisible();
    await expect(page.getByLabel('New course section', { exact: true })).toHaveValue(' Third section ');
    deny = false; await page.getByRole('button', { name: 'Add section', exact: true }).click();
    await expect(page.getByLabel('New course section', { exact: true })).toHaveValue('');
    expect(curriculum.sections[2]).toMatchObject({ title: 'Third section', lessons: [] });
    await page.getByLabel('New lesson', { exact: true }).fill(' Second lesson ');
    await page.getByLabel('Lesson section', { exact: true }).selectOption('s2');
    hold = true; release = undefined;
    await page.getByRole('button', { name: 'Add lesson', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Add section', exact: true })).toBeDisabled();
    await expect.poll(() => typeof release).toBe('function'); release(); hold = false;
    await expect(page.getByLabel('New lesson', { exact: true })).toHaveValue('');
    expect(curriculum.sections[1].lessons[0]).toMatchObject({ title: 'Second lesson', content: '' });
    await page.getByRole('button', { name: 'Move First section down', exact: true }).click();
    await expect.poll(() => curriculum.sections[0].id).toBe('s2');
    await expect(page.getByRole('button', { name: 'Move First section up', exact: true })).toBeEnabled();
    await page.getByLabel('Move Original lesson to', { exact: true }).selectOption('s2');
    await expect.poll(() => curriculum.sections.find(s => s.id === 's2').lessons.some(l => l.id === 'l1')).toBe(true);
    expect(curriculum.sections.find(s => s.id === 's2').lessons.find(l => l.id === 'l1').content).toBe('Full lesson content');
    await image('lms-curriculum-after-390');

    failCurriculum = true; await go(); await openCurriculum();
    await expect(page.getByRole('alert').filter({ hasText: 'Unable to load curriculum' })).toBeVisible();
    failCurriculum = false; await page.getByRole('button', { name: 'Retry curriculum', exact: true }).click();
    await expect(page.getByLabel('New course section', { exact: true })).toBeVisible();
    fail = true; await go('');
    await expect(page.getByRole('alert').filter({ hasText: 'Learning information could not load' })).toBeVisible();
    await expect(page.getByText('No courses published yet.', { exact: true })).toHaveCount(0);
    await expect(page.getByText('No learning activity yet.', { exact: true })).toHaveCount(0);
    await expect(page.locator('.hrms-lms-kpis')).toContainText('—');
    fail = false; await page.getByRole('button', { name: 'Retry learning', exact: true }).click();
    await expect(page.getByText('Employee #8', { exact: true })).toBeVisible();
    await expect(page.getByText('Certification and renewal data is not loaded.', { exact: true })).toBeVisible();
    const beforeReads = reads.length; await page.getByRole('button', { name: 'Refresh', exact: true }).click();
    await expect.poll(() => reads.length).toBeGreaterThanOrEqual(beforeReads + 2);
    expect(reads.some(p => /certifications|certification-renewals/.test(p))).toBe(false);

    for (const width of [481, 768, 1024, 1440]) {
      await page.setViewportSize({ width, height: 1000 }); await go();
      await expect(page.getByText('Employee #5', { exact: true })).toBeVisible();
      await expect(page.getByText('Employee #6', { exact: true })).toHaveCount(0);
      await expect(page.getByText('Certificate 4', { exact: true })).toBeVisible();
      await expect(page.getByText('Certificate 5', { exact: true })).toHaveCount(0);
      await expect(page.getByText('Certification #105', { exact: true })).toBeVisible();
      await expect(page.getByText('Certification #106', { exact: true })).toHaveCount(0);
      const geometry = () => page.locator('.hrms-lms-page').evaluate(e => { const r = e.getBoundingClientRect(); return { x: r.x, y: r.y, w: r.width, h: r.height }; });
      const before = await geometry();
      await page.evaluate(() => { for (const e of document.querySelectorAll('style')) if (e.getAttribute('data-vite-dev-id')?.endsWith('lms-mobile.css')) e.disabled = true; });
      expect(await geometry()).toEqual(before);
      await open(); await expect(page.locator('.smart-create-phone-sheet')).toHaveCount(0);
      await expect(page.getByLabel('xAPI Activity ID', { exact: true })).toBeVisible();
      await page.getByRole('dialog').press('Escape');
      await openCurriculum();
      await expect(page.getByLabel('New course section',{exact:true})).toHaveValue('');
      await expect(page.getByRole('button',{name:'Discard curriculum draft',exact:true})).toHaveCount(0);
      const desktopDrafts=()=>page.evaluate(()=>Object.fromEntries(Object.keys(sessionStorage).filter(key=>key.includes('hrms-lms-curriculum:')).map(key=>[key,sessionStorage.getItem(key)])));
      const beforeDesktopDrafts=await desktopDrafts();
      await page.getByLabel('New course section',{exact:true}).fill('Desktop existing behavior');
      expect(await desktopDrafts()).toEqual(beforeDesktopDrafts);
      expect(await page.locator('.hrms-lms-curriculum .move-columns').first().evaluate(e=>getComputedStyle(e).display)).toBe('flex');
    }
    expect(errors).toEqual([]);
    console.log('PASS LMS seven phones/all9coursefields+defaults/16px/5KPIs/all8loadedqueue records/overflow/curriculum controls;390dirty/403retry/pending/fullnumericpayload/reset, curriculum addsection+lesson/revision/order/crosssection+content/readretry, source errors/retry/refresh/disabledreads; draft course/table/route/reload recovery, actor+tenant+org+branch isolation, stale target/discard guards/late save ownership/storage failure; four desktop boundaries+5/4/5caps/nonphonesheet. All writes mocked.');
  } finally { await browser.close(); await server.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
