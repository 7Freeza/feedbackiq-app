import { initTokenField } from './token-field.js';
import { register, start } from './router.js';
import { initReportForm } from './report-form.js';
import { renderAnalyze } from './views/analyze.js';
import { renderDocs } from './views/docs.js';

initTokenField(document.getElementById('token-field'));
initReportForm();

register('/', renderAnalyze);
register('/docs', renderDocs);

start();
