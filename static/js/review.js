// ==================== Globals ====================
let activeQuill = null;
let activeEditorData = null;

// ==================== Fetch with retry ====================

async function fetchWithRetry(url, options, maxRetries) {
    maxRetries = maxRetries || 3;
    var lastError = null;
    for (var i = 0; i < maxRetries; i++) {
        try {
            var resp = await fetch(url, options);
            if (resp.ok) return resp;
            var body = await resp.json();
            if (body.error === '数据库忙，请重试') {
                lastError = new Error(body.error);
                await new Promise(function(r) { setTimeout(r, 500 * (i + 1)); });
                continue;
            }
            return resp;
        } catch (e) {
            lastError = e;
            if (i < maxRetries - 1) {
                await new Promise(function(r) { setTimeout(r, 500 * (i + 1)); });
            }
        }
    }
    throw lastError;
}

// ==================== Quill ====================

function createQuill(selector, content) {
    var ColorStyle = Quill.import('attributors/style/color');
    if (!ColorStyle.whitelist || ColorStyle.whitelist.indexOf('#C00000') === -1) {
        ColorStyle.whitelist = ['red','green','blue','#C00000','#c00000','#548235','#548235','#2E75B5','#2e75b5','#F0F0F0','#ffb700','#722ed1'];
        Quill.register(ColorStyle, true);
    }
    var q = new Quill(selector, { theme: 'snow', modules: { toolbar: false } });
    q.root.innerHTML = content || '';
    return q;
}

function fmtBold() { if (activeQuill) { var r = activeQuill.getSelection(); if (r) { var f = activeQuill.getFormat(r); activeQuill.formatText(r.index, r.length, 'bold', !f.bold); } } }
function fmtRed() { if (activeQuill) { var r = activeQuill.getSelection(); if (r && r.length > 0) activeQuill.formatText(r.index, r.length, 'color', '#C00000'); } }
function fmtGreen() { if (activeQuill) { var r = activeQuill.getSelection(); if (r && r.length > 0) activeQuill.formatText(r.index, r.length, 'color', '#548235'); } }
function fmtBlue() { if (activeQuill) { var r = activeQuill.getSelection(); if (r && r.length > 0) activeQuill.formatText(r.index, r.length, 'color', '#2E75B5'); } }
function fmtDel() { if (activeQuill) { var r = activeQuill.getSelection(); if (r) { var f = activeQuill.getFormat(r); activeQuill.formatText(r.index, r.length, 'strike', !f.strike); } } }

// ==================== Reference Text Rendering ====================

function renderRefText(el) {
    var text = el.getAttribute('data-original') || '';
    var fieldId = el.getAttribute('data-field-id');
    var urls = [];
    var statuses = {};
    var corrected = {};
    try { urls = JSON.parse(el.getAttribute('data-urls') || '[]'); } catch(e) {}
    try { statuses = JSON.parse(el.getAttribute('data-statuses') || '{}'); } catch(e) {}
    try { corrected = JSON.parse(el.getAttribute('data-corrected') || '{}'); } catch(e) {}

    if (!text) { el.innerHTML = '<span class=\"text-muted small\">无内容</span>'; return; }
    if (urls.length === 0) { el.innerHTML = escapeHtml(text).replace(/\n/g, '<br>'); return; }

    var html = '';
    var remaining = text;
    for (var i = 0; i < urls.length; i++) {
        var url = urls[i];
        var pos = remaining.indexOf(url);
        if (pos === -1) continue;
        html += escapeHtml(remaining.substring(0, pos));
        var st = statuses[url] || '';
        var cl = corrected[url] || '';
        html += '<span class="ref-link-inline">';
        html += '<a href="#" onclick="openLinkWindow(\'' + escapeAttr(url) + '\');return false;" class="ref-url-link" title="点击在右侧窗口打开">' + escapeHtml(url) + '</a> ';
        html += '<button class="ref-copy-btn" onclick="copyLink(\'' + escapeAttr(url) + '\',this);return false;" title="复制链接">\u{1F4CB}</button> ';
        html += '<select class="link-status-select" data-field-id="' + fieldId + '" data-url="' + escapeAttr(url) + '" onchange="saveLinkStatus(this)" style="font-size:10px;">';
        html += '<option value="">状态</option>';
        html += '<option value="有效"' + (st === '有效' ? ' selected' : '') + '>有效</option>';
        html += '<option value="打不开"' + (st === '打不开' ? ' selected' : '') + '>打不开</option>';
        html += '<option value="内容不符"' + (st === '内容不符' ? ' selected' : '') + '>内容不符</option>';
        html += '<option value="已过时"' + (st === '已过时' ? ' selected' : '') + '>已过时</option>';
        html += '</select> ';
        html += '<input type="text" class="corrected-link-input" placeholder="正确链接" data-field-id="' + fieldId + '" data-old-url="' + escapeAttr(url) + '" value="' + escapeAttr(cl) + '" onchange="saveLinkStatus(this)" style="font-size:10px;width:130px;display:' + (['打不开','内容不符','已过时'].indexOf(st) !== -1 ? 'inline-block' : 'none') + ';">';
        html += '</span>';
        remaining = remaining.substring(pos + url.length);
    }
    html += escapeHtml(remaining).replace(/\n/g, '<br>');
    el.innerHTML = html;
}

function extractUrlsForRef(text) {
    if (!text) return [];
    var matches = text.match(/https?:\/\/[^\s<>"'\\)\\]]+/g) || [];
    var seen = {};
    var unique = [];
    for (var i = 0; i < matches.length; i++) {
        var u = matches[i].replace(/[.,;:!?]+$/, '');
        if (!seen[u]) { seen[u] = true; unique.push(u); }
    }
    return unique;
}

function escapeHtml(s) { return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
function escapeAttr(s) { return s.replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

// ==================== Link Window ====================

function openLinkWindow(url) {
    var halfW = Math.floor(screen.width / 2);
    var name = 'review_link_window';
    var w = screen.width - halfW - 10;
    window.open(url, name, 'width=' + w + ',height=' + screen.height + ',left=' + (halfW + 5) + ',top=0,resizable=yes,scrollbars=yes');
}

// ==================== Copy Link ====================

function copyLink(url, btn) {
    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(url).then(function() { showCopyDone(btn); }).catch(function() { fallbackCopy(url, btn); });
    } else {
        fallbackCopy(url, btn);
    }
}

function fallbackCopy(url, btn) {
    var textarea = document.createElement('textarea');
    textarea.value = url;
    textarea.style.position = 'fixed';
    textarea.style.left = '-9999px';
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();
    try { document.execCommand('copy'); showCopyDone(btn); } catch(e) { alert('复制失败，请手动复制：\n' + url); }
    document.body.removeChild(textarea);
}

function showCopyDone(btn) {
    var orig = btn.textContent;
    btn.textContent = '✓';
    setTimeout(function() { btn.textContent = orig; }, 1500);
}

// ==================== Link Status ====================

function saveLinkStatus(el) {
    var fieldId = el.getAttribute('data-field-id');
    var linkStatuses = {};
    var correctedLinks = {};
    document.querySelectorAll('.link-status-select[data-field-id="' + fieldId + '"]').forEach(function(s) {
        if (s.value) linkStatuses[s.dataset.url] = s.value;
    });
    document.querySelectorAll('.corrected-link-input[data-field-id="' + fieldId + '"]').forEach(function(inp) {
        if (inp.value.trim()) correctedLinks[inp.dataset.oldUrl] = inp.value.trim();
    });
    document.querySelectorAll('.link-status-select[data-field-id="' + fieldId + '"]').forEach(function(s) {
        var row = s.closest('.ref-link-inline');
        var inp = row ? row.querySelector('.corrected-link-input') : null;
        if (inp) inp.style.display = ['打不开','内容不符','已过时'].indexOf(s.value) !== -1 ? 'inline-block' : 'none';
    });
    fetchWithRetry('/api/review/' + fieldId + '/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ link_statuses: linkStatuses, corrected_links: correctedLinks })
    }).catch(function(e) { console.error(e); });
}

// ==================== Tabs ====================

function switchPair(idx) {
    document.querySelectorAll('.pair-tab').forEach(function(t) { t.classList.remove('active'); });
    var tabs = document.querySelectorAll('.pair-tab');
    if (tabs[idx]) tabs[idx].classList.add('active');
    document.querySelectorAll('.pair-panel').forEach(function(p) { p.classList.add('d-none'); });
    var panel = document.getElementById('pairPanel' + idx);
    if (panel) panel.classList.remove('d-none');
    closeAllEditors();
}

// ==================== Init ====================

document.addEventListener('DOMContentLoaded', function() {
    restoreViewState();
    initAllRefTexts();
    initContentDisplays();
    bindAllEvents();
});

function initAllRefTexts() {
    document.querySelectorAll('.ref-text').forEach(function(el) {
        if (el.getAttribute('data-original')) renderRefText(el);
    });
}

function initContentDisplays() {
    document.querySelectorAll('.btn-toggle-original').forEach(function(btn) {
        var fieldId = btn.getAttribute('data-field-id');
        if (!fieldId) return;
        var panelType = btn.getAttribute('data-panel-type') || 'content';
        var editBtn = document.querySelector('.btn-edit-panel[data-field-id="' + fieldId + '"][data-panel-type="' + panelType + '"]');
        if (!editBtn) { btn.style.display = 'none'; return; }
        var changed = editBtn.getAttribute('data-changed') || '';
        var original = editBtn.getAttribute('data-original') || '';
        btn.style.display = (changed && changed !== original) ? '' : 'none';
    });
}

function bindAllEvents() {
    // Edit buttons
    document.querySelectorAll('.btn-edit-panel').forEach(function(btn) {
        btn.addEventListener('click', function() {
            var fieldId = this.dataset.fieldId;
            var pairIdx = this.dataset.pairIdx;
            var panelType = this.dataset.panelType;
            var original = this.dataset.original || '';
            var changed = this.dataset.changed || '';
            var note = this.dataset.note || '';
            startEdit(pairIdx, panelType, fieldId, changed || original, note);
        });
    });

    // Save buttons
    document.querySelectorAll('[id^="btnContentSave"], [id^="btnRefSave"]').forEach(function(btn) {
        btn.addEventListener('click', function() { saveEdit(); });
    });

    // Cancel buttons
    document.querySelectorAll('.btn-cancel-edit').forEach(function(btn) {
        btn.addEventListener('click', function() { cancelEdit(); });
    });

    // Status buttons
    document.querySelectorAll('.status-btn').forEach(function(btn) {
        btn.addEventListener('click', async function() {
            var fieldId = this.dataset.fieldId;
            var status = this.dataset.status;
            if (!fieldId || fieldId === '0') return;
            try {
                var resp = await fetchWithRetry('/api/review/' + fieldId + '/save', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ status: status })
                });
                var result = await resp.json();
                if (result.ok) {
                    showSaved();
                    updateStatusButtons(fieldId, status);
                    setTimeout(function() {
                        saveViewState();
                        location.reload();
                    }, 400);
                }
            } catch(e) {}
        });
    });

    // Toggle buttons
    document.querySelectorAll('.btn-toggle-original').forEach(function(btn) {
        btn.addEventListener('click', function() {
            toggleContentOriginal(this.dataset.fieldId);
        });
    });
}

// ==================== Editor ====================

function startEdit(pairIdx, panelType, fieldId, content, note) {
    closeAllEditors();
    var viewId = (panelType === 'content' ? 'contentView' : 'refView') + pairIdx;
    var editId = (panelType === 'content' ? 'contentEdit' : 'refEdit') + pairIdx;
    var editorId = (panelType === 'content' ? 'contentEditor' : 'refEditor') + pairIdx;
    var noteId = (panelType === 'content' ? 'contentNote' : 'refNote') + pairIdx;

    document.getElementById(viewId).style.display = 'none';
    document.getElementById(editId).style.display = 'block';
    var noteEl = document.getElementById(noteId);
    if (noteEl) noteEl.value = note || '';

    activeQuill = createQuill('#' + editorId, content);
    activeEditorData = { pairIdx: pairIdx, panelType: panelType, fieldId: fieldId, viewId: viewId, editId: editId, noteId: noteId };
}

function cancelEdit() {
    if (!activeEditorData) return;
    document.getElementById(activeEditorData.viewId).style.display = '';
    document.getElementById(activeEditorData.editId).style.display = 'none';
    activeQuill = null;
    activeEditorData = null;
}

async function saveEdit() {
    if (!activeEditorData || !activeQuill) return;
    var d = activeEditorData;
    var html = activeQuill.root.innerHTML;
    var noteEl = document.getElementById(d.noteId);
    var note = noteEl ? noteEl.value : '';

    try {
        var resp = await fetchWithRetry('/api/review/' + d.fieldId + '/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ changed_content: html, internal_note: note })
        });
        var result = await resp.json();
        if (result.ok) {
            showSaved();
            document.getElementById(d.viewId).style.display = '';
            document.getElementById(d.editId).style.display = 'none';
            var viewDiv = document.getElementById(d.viewId).querySelector('.formatted-text');
            if (viewDiv) viewDiv.innerHTML = html;

            // Update edit button data for toggle
            var editBtn = document.querySelector('.btn-edit-panel[data-field-id="' + d.fieldId + '"][data-panel-type="' + d.panelType + '"]');
            if (editBtn) {
                editBtn.setAttribute('data-changed', html);
                if (d.panelType === 'reference') {
                    var plainText = html.replace(/<[^>]*>/g, '');
                    editBtn.setAttribute('data-original', plainText);
                }
            }

            // For reference: update link data and re-render
            if (d.panelType === 'reference') {
                var refEl = document.getElementById(d.viewId).querySelector('.ref-text');
                if (refEl) {
                    var plainText = html.replace(/<[^>]*>/g, '');
                    refEl.setAttribute('data-original', plainText);
                    var newUrls = extractUrlsForRef(plainText);
                    refEl.setAttribute('data-urls', JSON.stringify(newUrls));
                    renderRefText(refEl);
                }
            }

            var toggleBtn = document.getElementById('toggleBtn' + d.fieldId);
            if (toggleBtn) toggleBtn.style.display = '';
            activeQuill = null;
            activeEditorData = null;
        }
    } catch(e) { alert('保存失败'); }
}

function closeAllEditors() {
    if (activeEditorData) {
        document.getElementById(activeEditorData.viewId).style.display = '';
        document.getElementById(activeEditorData.editId).style.display = 'none';
        activeQuill = null;
        activeEditorData = null;
    }
}

function showSaved() {
    var el = document.getElementById('saveStatus');
    if (el) { el.style.display = ''; setTimeout(function() { el.style.display = 'none'; }, 2000); }
}

// ==================== Toggle ====================

function toggleContentOriginal(fieldId) {
    var toggleBtn = document.getElementById('toggleBtn' + fieldId);
    if (!toggleBtn) return;
    var panelType = toggleBtn.getAttribute('data-panel-type') || 'content';
    var textEl = document.getElementById((panelType === 'reference' ? 'refText' : 'contentText') + fieldId);
    if (!textEl) return;
    var editBtn = document.querySelector('.btn-edit-panel[data-field-id="' + fieldId + '"][data-panel-type="' + panelType + '"]');
    var original = editBtn ? editBtn.dataset.original : '';
    var changed = editBtn ? editBtn.dataset.changed : '';

    if (toggleBtn.textContent.indexOf('原文') !== -1) {
        if (panelType === 'reference') { renderRefText(textEl); }
        else { textEl.innerHTML = original.replace(/\n/g, '<br>'); }
        toggleBtn.textContent = '查看修改';
    } else {
        textEl.innerHTML = changed || original.replace(/\n/g, '<br>');
        toggleBtn.textContent = '查看原文';
    }
}

// ==================== Status ====================

function updateStatusButtons(fieldId, status) {
    document.querySelectorAll('.status-btn[data-field-id="' + fieldId + '"]').forEach(function(b) {
        b.classList.remove('active');
        if (b.dataset.status === status) b.classList.add('active');
    });
}

// ==================== Tree ====================

function toggleTreeNode(el) {
    el.classList.toggle('collapsed');
    var l2s = el.parentElement.querySelector('.tree-l2s');
    if (l2s) l2s.style.display = l2s.style.display === 'none' ? '' : 'none';
}

function navigateToIdx(projectId, idx) {
    window.location.href = '/projects/' + projectId + '/review?l2=' + idx;
}

function togglePrompt() {
    var col = document.getElementById('promptCol');
    var mainCol = document.getElementById('mainCol');
    if (!col || !mainCol) return;
    if (col.style.display === 'none') {
        col.style.display = '';
        mainCol.style.maxWidth = 'calc(100% - 180px - 350px)';
        generatePrompt();
    } else {
        col.style.display = 'none';
        mainCol.style.maxWidth = 'calc(100% - 180px)';
    }
}

function generatePrompt() {
    var promptTemplate = document.getElementById('promptText');
    if (!promptTemplate) return;

    // Get current active pair
    var activeTab = document.querySelector('.pair-tab.active');
    var pairIdx = activeTab ? activeTab.getAttribute('data-pair') : '0';
    var panel = document.getElementById('pairPanel' + pairIdx);
    if (!panel) return;

    // Get content text
    var contentView = panel.querySelector('.content-view');
    var contentText = contentView ? (contentView.textContent || '').trim() : '';

    // Get reference URLs
    var refTextEl = panel.querySelector('.ref-text');
    var urls = [];
    if (refTextEl) {
        var dataUrls = refTextEl.getAttribute('data-urls');
        if (dataUrls) {
            try { urls = JSON.parse(dataUrls); } catch(e) {}
        }
    }

    var prompt = '【任务】\n请根据我提供的有效链接，逐条核对以下信息的准确性。\n\n';
    prompt += '【核对规则】\n';
    prompt += '一、逐项判断标准\n';
    prompt += '判断结论\t适用情形\n';
    prompt += '正确\t链接原文能完整支持该信息\n';
    prompt += '错误\t信息与链接原文矛盾、数据有误、错误引用条文\n';
    prompt += '错误+缺漏\t信息同时存在错误和遗漏\n';
    prompt += '缺漏\t核心正确，但漏掉了关键限定条件\n';
    prompt += '未找到\t在所有链接中均无直接原文依据\n';
    prompt += '推断成立\t无直接原文但可通过多条链接组合推断\n\n';
    prompt += '二、拆分处理\n';
    prompt += '● 如一条信息包含多个独立主张，需逐项拆分判断\n\n';
    prompt += '三、数据核验\n';
    prompt += '● 优先核验法律条款编号、日期、数字比例等硬性数据\n\n';
    prompt += '四、上下文检查\n';
    prompt += '● 检查是否存在过度泛化，补充原文限定条件\n\n';
    prompt += '五、链接矛盾处理\n';
    prompt += '● 以权威性更高、时效性更新的来源为准\n\n';
    prompt += '六、否定性信息记录\n';
    prompt += '● 判断为"未找到"或"错误"，需指出"该内容未出现在链接X中"\n\n';
    prompt += '七、推断成立的标注\n';
    prompt += '● 说明推断链条\n\n';
    prompt += '八、时效性风险标注\n';
    prompt += '● 3年以上链接需标注"建议与最新法规交叉验证"\n\n';
    prompt += '九、外部引用检查\n';
    prompt += '● 超链接需说明是否可访问及内容匹配\n\n';
    prompt += '【输出格式】\n';
    prompt += '【信息序号X】\n 判断：[正确/错误/错误+缺漏/缺漏/未找到/推断成立]\n';
    prompt += ' 溯源：[链接编号]\n 说明：\n\n';
    prompt += '【待核对信息】\n' + contentText + '\n\n';
    prompt += '【参考链接】\n';
    for (var i = 0; i < urls.length; i++) {
        prompt += '链接' + (i+1) + '：' + urls[i] + '\n';
    }

    promptTemplate.value = prompt;
}

function copyPrompt() {
    var textarea = document.getElementById('promptText');
    if (!textarea) return;
    textarea.select();
    document.execCommand('copy');
    var btn = event.target;
    var orig = btn.textContent;
    btn.textContent = '✓ 已复制';
    setTimeout(function() { btn.textContent = orig; }, 2000);
}

function toggleSidebar() {
    var col = document.getElementById('sidebarCol');
    var tree = document.getElementById('sidebarTree');
    var btn = document.getElementById('sidebarToggleBtn');
    if (tree.style.display === 'none') {
        col.style.width = '180px';
        tree.style.display = '';
        if (btn) btn.textContent = '«';
        sessionStorage.setItem('sidebarCollapsed', '0');
    } else {
        col.style.width = '0';
        tree.style.display = 'none';
        if (btn) btn.textContent = '»';
        sessionStorage.setItem('sidebarCollapsed', '1');
    }
}

function saveViewState() {
    // 记住当前 Tab
    var activeTab = document.querySelector('.pair-tab.active');
    if (activeTab) {
        sessionStorage.setItem('activePairTab', activeTab.getAttribute('data-pair'));
    }
    // 记住侧边栏状态
    var tree = document.getElementById('sidebarTree');
    if (tree && tree.style.display === 'none') {
        sessionStorage.setItem('sidebarCollapsed', '1');
    } else {
        sessionStorage.setItem('sidebarCollapsed', '0');
    }
}

function restoreViewState() {
    // 恢复 Tab
    var savedTab = sessionStorage.getItem('activePairTab');
    if (savedTab && savedTab !== '0') {
        switchPair(parseInt(savedTab));
    }
    // 恢复侧边栏
    if (sessionStorage.getItem('sidebarCollapsed') === '1') {
        var col = document.getElementById('sidebarCol');
        var tree = document.getElementById('sidebarTree');
        var btn = document.getElementById('sidebarToggleBtn');
        if (col) col.style.width = '0';
        if (tree) tree.style.display = 'none';
        if (btn) btn.textContent = '»';
    }
}

// ==================== Keyboard ====================

document.addEventListener('keydown', function(e) {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
    if (e.target.closest && e.target.closest('.ql-editor')) return;
    if (e.key === '1') clickStatus('待审阅');
    if (e.key === '2') clickStatus('已确认');
    if (e.key === '3') clickStatus('需修改');
    if (e.key === '4') clickStatus('待讨论');
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
        var nb = document.querySelector('a.btn-outline-primary:not(.disabled)');
        if (nb && nb.textContent.indexOf('下一') !== -1) nb.click();
    }
    if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
        var pb = document.querySelector('a.btn-outline-secondary:not(.disabled)');
        if (pb && pb.textContent.indexOf('上一') !== -1) pb.click();
    }
    if (e.key === 'Escape') cancelEdit();
});

function clickStatus(status) {
    var btns = document.querySelectorAll('.status-btn[data-status="' + status + '"]');
    for (var i = 0; i < btns.length; i++) {
        if (btns[i].offsetParent !== null && btns[i].dataset.fieldId !== '0') { btns[i].click(); return; }
    }
}
