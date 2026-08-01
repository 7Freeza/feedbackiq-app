import { initTokenField } from './token-field.js';
import { register, start } from './router.js';
import { renderAnalyze } from './views/analyze.js';
import { renderDocs } from './views/docs.js';

initTokenField(document.getElementById('token-field'));

register('/', renderAnalyze);
register('/docs', renderDocs);

start();
