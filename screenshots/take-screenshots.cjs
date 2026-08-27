const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });

  // === MOBILE VIEW (390x844) ===
  const mobileCtx = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 2,
    userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)',
  });
  const mobilePage = await mobileCtx.newPage();

  // Set fake cached session to bypass BrowserGate
  await mobilePage.addInitScript(() => {
    localStorage.setItem('oxycode_token', 'fake-dev-token');
    localStorage.setItem('oxycode_user', JSON.stringify({ id: 8972944701, username: 'testuser', firstName: 'Test' }));
    localStorage.setItem('oxycode_session_id', 'dev-session');
  });

  // 1. Home page mobile
  await mobilePage.goto('http://localhost:5173', { waitUntil: 'networkidle', timeout: 30000 });
  await mobilePage.waitForTimeout(3000);
  await mobilePage.screenshot({ path: 'C:\\Users\\Teleforge\\Desktop\\OXYCODE AI BOT\\screenshots\\01-home-mobile.png', fullPage: false });
  console.log('Screenshot 1: Home mobile');

  // 2. Click hamburger menu button (the ListIcon button in header)
  try {
    const headerBtn = mobilePage.locator('header button').first();
    await headerBtn.waitFor({ state: 'visible', timeout: 3000 });
    await headerBtn.click();
    await mobilePage.waitForTimeout(1000);
    await mobilePage.screenshot({ path: 'C:\\Users\\Teleforge\\Desktop\\OXYCODE AI BOT\\screenshots\\02-menu-open-mobile.png', fullPage: false });
    console.log('Screenshot 2: Mobile menu open');
  } catch (e) {
    console.log('Screenshot 2: Menu button not found, skipping');
  }

  // 3. Chat page mobile with agent selector
  await mobilePage.goto('http://localhost:5173/chat/new?agent=oxygent', { waitUntil: 'networkidle', timeout: 30000 });
  await mobilePage.waitForTimeout(3000);
  await mobilePage.screenshot({ path: 'C:\\Users\\Teleforge\\Desktop\\OXYCODE AI BOT\\screenshots\\03-chat-mobile.png', fullPage: false });
  console.log('Screenshot 3: Chat page mobile');

  // === DESKTOP VIEW (1440x900) ===
  const desktopCtx = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
  });
  const desktopPage = await desktopCtx.newPage();
  await desktopPage.addInitScript(() => {
    localStorage.setItem('oxycode_token', 'fake-dev-token');
    localStorage.setItem('oxycode_user', JSON.stringify({ id: 8972944701, username: 'testuser', firstName: 'Test' }));
    localStorage.setItem('oxycode_session_id', 'dev-session');
  });

  // 4. Home page desktop
  await desktopPage.goto('http://localhost:5173', { waitUntil: 'networkidle', timeout: 30000 });
  await desktopPage.waitForTimeout(3000);
  await desktopPage.screenshot({ path: 'C:\\Users\\Teleforge\\Desktop\\OXYCODE AI BOT\\screenshots\\04-home-desktop.png', fullPage: false });
  console.log('Screenshot 4: Home desktop');

  // 5. Desktop sidebar
  try {
    const trigger = desktopPage.locator('button[data-sidebar="trigger"]').first();
    await trigger.waitFor({ state: 'visible', timeout: 3000 });
    await trigger.click();
    await desktopPage.waitForTimeout(800);
    await desktopPage.screenshot({ path: 'C:\\Users\\Teleforge\\Desktop\\OXYCODE AI BOT\\screenshots\\05-sidebar-desktop.png', fullPage: false });
    console.log('Screenshot 5: Desktop sidebar');
  } catch (e) {
    console.log('Screenshot 5: Sidebar trigger not found, skipping');
  }

  // 6. Chat page desktop
  await desktopPage.goto('http://localhost:5173/chat/new?agent=debugger', { waitUntil: 'networkidle', timeout: 30000 });
  await desktopPage.waitForTimeout(3000);
  await desktopPage.screenshot({ path: 'C:\\Users\\Teleforge\\Desktop\\OXYCODE AI BOT\\screenshots\\06-chat-desktop.png', fullPage: false });
  console.log('Screenshot 6: Chat desktop');

  await browser.close();
  console.log('All screenshots saved!');
})();
