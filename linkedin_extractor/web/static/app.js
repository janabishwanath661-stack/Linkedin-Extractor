/**
 * app.js — Frontend logic for the LinkedIn Profile Extractor.
 *
 * Handles form submission, SSE progress streaming, result rendering,
 * tab switching, screenshot lightbox, and JSON copying.
 */

// ── DOM References ────────────────────────────────────────────────────────────
const searchForm      = document.getElementById('searchForm');
const searchInput     = document.getElementById('searchInput');
const searchBtn       = document.getElementById('searchBtn');
const errorBanner     = document.getElementById('errorBanner');
const errorMessage    = document.getElementById('errorMessage');
const progressPanel   = document.getElementById('progressPanel');
const progressList    = document.getElementById('progressList');
const progressTitle   = document.getElementById('progressTitle');
const progressSpinner = document.getElementById('progressSpinner');
const resultsSection  = document.getElementById('resultsSection');
const profileCard     = document.getElementById('profileCard');
const screenshotGallery = document.getElementById('screenshotGallery');
const jsonOutput      = document.getElementById('jsonOutput');
const copyJsonBtn     = document.getElementById('copyJsonBtn');
const lightbox        = document.getElementById('lightbox');
const lightboxImg     = document.getElementById('lightboxImg');
const resultTabs      = document.getElementById('resultTabs');


// ── Form Submit ───────────────────────────────────────────────────────────────
searchForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const query = searchInput.value.trim();
  if (!query) return;

  resetUI();
  searchBtn.disabled = true;
  searchBtn.innerHTML = '<span class="spinner"></span> Extracting...';

  try {
    const res = await fetch('/api/extract', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query }),
    });

    if (!res.ok) {
      throw new Error(`Server error: ${res.status}`);
    }

    const { job_id } = await res.json();
    listenProgress(job_id);
  } catch (err) {
    showError(err.message);
    resetButton();
  }
});


// ── SSE Progress Listener ─────────────────────────────────────────────────────
function listenProgress(jobId) {
  progressPanel.classList.add('visible');
  const source = new EventSource(`/api/progress/${jobId}`);

  source.onmessage = (event) => {
    const data = JSON.parse(event.data);

    if (data.type === 'progress') {
      addProgressItem(data.message, data.step);
    }

    if (data.type === 'done') {
      source.close();
      progressSpinner.style.display = 'none';
      progressTitle.textContent = data.error ? 'Extraction failed' : 'Extraction complete ✓';

      if (data.error) {
        showError(data.error);
      } else {
        renderResults(data.profile, data.screenshots);
      }
      resetButton();
    }
  };

  source.onerror = () => {
    source.close();
    showError('Lost connection to server. Please try again.');
    resetButton();
  };
}


// ── Progress Item ─────────────────────────────────────────────────────────────
function addProgressItem(message, step) {
  // Mark previous active item as done
  const prevActive = progressList.querySelector('.progress__item--active');
  if (prevActive) {
    prevActive.classList.remove('progress__item--active');
    prevActive.classList.add('progress__item--done');
  }

  const li = document.createElement('li');
  const cls = step === 'error' ? 'progress__item--error' : 'progress__item--active';
  li.className = `progress__item ${cls}`;
  li.innerHTML = `<span class="progress__dot"></span><span>${escapeHtml(message)}</span>`;
  progressList.appendChild(li);
  progressList.scrollTop = progressList.scrollHeight;
}


// ── Render Results ────────────────────────────────────────────────────────────
function renderResults(profile, screenshots) {
  resultsSection.classList.add('visible');

  // ── Profile Tab ─────────────────
  if (profile) {
    const initials = (profile.full_name || '??').split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);

    let html = `
      <div class="profile-card__header">
        <div class="profile-card__avatar">${initials}</div>
        <div>
          <div class="profile-card__name">${escapeHtml(profile.full_name || 'Unknown')}</div>
          <div class="profile-card__headline">${escapeHtml(profile.headline || '')}</div>
          <div class="profile-card__location">📍 ${escapeHtml(profile.location || 'N/A')}</div>
        </div>
      </div>
    `;

    // About
    if (profile.about) {
      html += `
        <div class="detail-section" style="margin-bottom: 20px;">
          <div class="detail-section__title">About</div>
          <p style="color: var(--text-secondary); font-size: 14px; line-height: 1.7;">${escapeHtml(profile.about)}</p>
        </div>
      `;
    }

    html += '<div class="detail-grid">';

    // Experience
    if (profile.experience && profile.experience.length) {
      html += `<div class="detail-section"><div class="detail-section__title">Experience</div>`;
      for (const exp of profile.experience) {
        html += `
          <div class="timeline-item">
            <div class="timeline-item__title">${escapeHtml(exp.title || '')}</div>
            <div class="timeline-item__company">${escapeHtml(exp.company || '')}</div>
            <div class="timeline-item__meta">${escapeHtml(exp.start_date || '')} – ${escapeHtml(exp.end_date || 'Present')}${exp.location ? ' · ' + escapeHtml(exp.location) : ''}</div>
            ${exp.description ? `<div class="timeline-item__desc">${escapeHtml(exp.description)}</div>` : ''}
          </div>
        `;
      }
      html += '</div>';
    }

    // Education
    if (profile.education && profile.education.length) {
      html += `<div class="detail-section"><div class="detail-section__title">Education</div>`;
      for (const edu of profile.education) {
        html += `
          <div class="timeline-item">
            <div class="timeline-item__title">${escapeHtml(edu.institution || '')}</div>
            <div class="timeline-item__company">${escapeHtml(edu.degree || '')}${edu.field_of_study ? ' — ' + escapeHtml(edu.field_of_study) : ''}</div>
            <div class="timeline-item__meta">${escapeHtml(edu.start_year || '')} – ${escapeHtml(edu.end_year || '')}</div>
          </div>
        `;
      }
      html += '</div>';
    }

    // Skills
    if (profile.skills && profile.skills.length) {
      html += `<div class="detail-section"><div class="detail-section__title">Skills</div><div class="tag-list">`;
      for (const skill of profile.skills) {
        html += `<span class="tag">${escapeHtml(skill)}</span>`;
      }
      html += '</div></div>';
    }

    // Certifications
    if (profile.certifications && profile.certifications.length) {
      html += `<div class="detail-section"><div class="detail-section__title">Certifications</div>`;
      for (const cert of profile.certifications) {
        html += `
          <div class="timeline-item">
            <div class="timeline-item__title">${escapeHtml(cert.name || '')}</div>
            <div class="timeline-item__company">${escapeHtml(cert.issuer || '')}</div>
            ${cert.issue_date ? `<div class="timeline-item__meta">${escapeHtml(cert.issue_date)}</div>` : ''}
          </div>
        `;
      }
      html += '</div>';
    }

    // Languages
    if (profile.languages && profile.languages.length) {
      html += `<div class="detail-section"><div class="detail-section__title">Languages</div><div class="tag-list">`;
      for (const lang of profile.languages) {
        html += `<span class="tag">${escapeHtml(lang)}</span>`;
      }
      html += '</div></div>';
    }

    // Contact Info
    const contactFields = [];
    if (profile.email) contactFields.push(`📧 ${profile.email}`);
    if (profile.phone) contactFields.push(`📞 ${profile.phone}`);
    if (profile.website) contactFields.push(`🌐 ${profile.website}`);
    if (contactFields.length) {
      html += `<div class="detail-section"><div class="detail-section__title">Contact</div>`;
      for (const c of contactFields) {
        html += `<div style="color: var(--text-secondary); font-size: 14px; padding: 4px 0;">${escapeHtml(c)}</div>`;
      }
      html += '</div>';
    }

    html += '</div>'; // close detail-grid
    profileCard.innerHTML = html;

    // JSON tab
    jsonOutput.textContent = JSON.stringify(profile, null, 2);
  }

  // ── Screenshots Tab ─────────────
  if (screenshots && screenshots.length) {
    screenshotGallery.innerHTML = '';
    for (const src of screenshots) {
      const label = src.split('/').pop().replace('.png', '').replace(/_/g, ' · ');
      const item = document.createElement('div');
      item.className = 'gallery__item';
      item.innerHTML = `
        <img src="${src}" alt="${label}" loading="lazy" />
        <div class="gallery__label">${escapeHtml(label)}</div>
      `;
      item.addEventListener('click', () => openLightbox(src));
      screenshotGallery.appendChild(item);
    }
  }
}


// ── Tab Switching ─────────────────────────────────────────────────────────────
resultTabs.addEventListener('click', (e) => {
  const tab = e.target.closest('.results__tab');
  if (!tab) return;

  document.querySelectorAll('.results__tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.results__panel').forEach(p => p.classList.remove('active'));

  tab.classList.add('active');
  const panel = document.getElementById(`tab-${tab.dataset.tab}`);
  if (panel) panel.classList.add('active');
});


// ── Lightbox ──────────────────────────────────────────────────────────────────
function openLightbox(src) {
  lightboxImg.src = src;
  lightbox.classList.add('visible');
}

lightbox.addEventListener('click', () => {
  lightbox.classList.remove('visible');
  lightboxImg.src = '';
});

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') lightbox.classList.remove('visible');
});


// ── Copy JSON ─────────────────────────────────────────────────────────────────
copyJsonBtn.addEventListener('click', () => {
  navigator.clipboard.writeText(jsonOutput.textContent).then(() => {
    copyJsonBtn.textContent = 'Copied!';
    setTimeout(() => { copyJsonBtn.textContent = 'Copy'; }, 2000);
  });
});


// ── Helpers ───────────────────────────────────────────────────────────────────
function resetUI() {
  errorBanner.classList.remove('visible');
  progressPanel.classList.remove('visible');
  resultsSection.classList.remove('visible');
  progressList.innerHTML = '';
  progressSpinner.style.display = '';
  progressTitle.textContent = 'Extraction in progress...';
  profileCard.innerHTML = '';
  screenshotGallery.innerHTML = '';
  jsonOutput.textContent = '';
}

function resetButton() {
  searchBtn.disabled = false;
  searchBtn.textContent = 'Extract Profile';
}

function showError(msg) {
  errorMessage.textContent = msg;
  errorBanner.classList.add('visible');
}

function escapeHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
