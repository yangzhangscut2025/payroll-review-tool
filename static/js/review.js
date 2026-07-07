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
        ColorStyle.whitelist = ['red','green','blue','#C00000','#c00000','#548235','#548235','#2E75B5','#2e75b5','#F0F0F0','#FFC000','#5B9BD5'];
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
                    setTimeout(function() { location.reload(); }, 400);
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

function toggleSidebar() {
    var col = document.getElementById('sidebarCol');
    var tree = document.getElementById('sidebarTree');
    var btn = document.getElementById('sidebarToggleBtn');
    if (tree.style.display === 'none') {
        col.style.width = '180px';
        tree.style.display = '';
        if (btn) btn.textContent = '«';
    } else {
        col.style.width = '0';
        tree.style.display = 'none';
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
