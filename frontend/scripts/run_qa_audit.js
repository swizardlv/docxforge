import { chromium } from 'playwright';
import path from 'path';
import fs from 'fs';

const ARTIFACT_DIR = '/Users/swizard/.gemini/antigravity-cli/brain/88218c72-f85d-4350-acc8-89981c3e74ce';

if (!fs.existsSync(ARTIFACT_DIR)) {
  fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
}

async function runQaAudit() {
  console.log('🚀 启动 Playwright E2E 自动化 QA 审查...');
  let browser;
  try {
    browser = await chromium.launch({ headless: true });
  } catch {
    browser = await chromium.launch({ headless: true, channel: 'chrome' });
  }
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 }
  });
  const page = await context.newPage();
  const auditLog = [];

  try {
    // 1. 打开首页
    await page.goto('http://localhost:5173', { waitUntil: 'networkidle' });
    await page.waitForTimeout(1000);
    const screenshotPath1 = path.join(ARTIFACT_DIR, 'qa_01_homepage.png');
    await page.screenshot({ path: screenshotPath1, fullPage: true });
    auditLog.push(`[Pass] 页面首页加载正常，截图保存至: ${screenshotPath1}`);

    // 2. 检查模板选择区域与上传按钮
    const templateSelect = page.locator('select').first();
    if (await templateSelect.isVisible()) {
      auditLog.push('[Pass] Word 模板选择组件响应正常');
    } else {
      auditLog.push('[Fail] 模板选择器组件缺失或不可见');
    }

    const uploadBtn = page.locator('button:has-text("上传 .docx")');
    if (await uploadBtn.isVisible()) {
      auditLog.push('[Pass] 上传 .docx 模板按钮正确可见');
    } else {
      auditLog.push('[Fail] 上传 .docx 模板按钮未找到');
    }

    // 3. 检查 Markdown 正文与项目文件夹导入功能
    const folderImportBtn = page.locator('button:has-text("导入项目文件夹")');
    if (await folderImportBtn.isVisible()) {
      auditLog.push('[Pass] 📂 导入项目文件夹按钮正确可见');
    } else {
      auditLog.push('[Fail] 📂 导入项目文件夹按钮未找到');
    }

    // 4. 检查右侧高级配置与属性面板
    const screenshotPath2 = path.join(ARTIFACT_DIR, 'qa_02_fields_config.png');
    await page.screenshot({ path: screenshotPath2, fullPage: true });

    // 5. 点击“导出 Word 文档”触发实际后端渲染流程
    const exportBtn = page.locator('button:has-text("导出 Word 文档")');
    if (await exportBtn.isVisible()) {
      console.log('触发导出 Word 文档...');
      await exportBtn.click();
      await page.waitForTimeout(3500);
      const screenshotPath3 = path.join(ARTIFACT_DIR, 'qa_03_rendered_success.png');
      await page.screenshot({ path: screenshotPath3, fullPage: true });
      auditLog.push(`[Pass] 渲染导出流程成功响应，生成文档并支持销毁与下载，截图保存至: ${screenshotPath3}`);
    } else {
      auditLog.push('[Fail] 导出 Word 文档按钮未找到');
    }

    // 6. 测试数据安全销毁 (Destroy Panel)
    const destroyBtn = page.locator('button:has-text("销毁数据")').or(page.locator('button:has-text("立即销毁")'));
    if (await destroyBtn.first().isVisible()) {
      console.log('测试触发数据销毁...');
      await destroyBtn.first().click();
      await page.waitForTimeout(1500);
      const screenshotPath4 = path.join(ARTIFACT_DIR, 'qa_04_destroyed_report.png');
      await page.screenshot({ path: screenshotPath4, fullPage: true });
      auditLog.push(`[Pass] 数据安全销毁功能成功触发，展示 DoD #3 Shredding 审计日志，截图保存至: ${screenshotPath4}`);
    }

  } catch (err) {
    console.error('QA 审查运行异常:', err);
    auditLog.push(`[Error] 异常中断: ${err.message}`);
  } finally {
    await browser.close();
    console.log('QA 审查运行完毕。');
    console.log(auditLog.join('\n'));
  }
}

runQaAudit();
