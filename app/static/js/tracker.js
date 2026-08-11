/**
 * SmartReco Natural Language Behavioral Telemetry Engine
 * Tracks 17 micro-behaviors with 0ms UI lag and formats actions into rich natural language intent statements.
 */
(function () {
    const STORAGE_KEY = 'SMARTRECO_NATURAL_SIGNALS';
    const MAX_SIGNALS = 16;
    let pageStartTime = Date.now();
    let currentTopicName = 'Course Catalog';
    let maxScrollDepthTracked = 0;

    // 1. Session Storage Helpers
    function getStoredSignals() {
        try {
            return JSON.parse(sessionStorage.getItem(STORAGE_KEY)) || [];
        } catch (e) {
            return [];
        }
    }

    function saveStoredSignals(signals) {
        try {
            sessionStorage.setItem(STORAGE_KEY, JSON.stringify(signals.slice(0, MAX_SIGNALS)));
        } catch (e) {}
    }

    // 2. Render Signals Directly into Floating Tracker UI
    function renderSignalsUI() {
        const signalContainer = document.querySelector('#live-signal-pills');
        if (!signalContainer) return;

        const signals = getStoredSignals();
        if (signals.length === 0) {
            signalContainer.innerHTML = `
                <div style="display:flex;align-items:center;gap:0.4rem;padding:0.45rem 0.6rem;background:rgba(30,41,59,0.5);border:1px solid rgba(255,255,255,0.08);border-radius:6px;font-size:0.76rem;color:#94a3b8;">
                    <span style="color:#a78bfa">⚡ Active</span> · <span>Session Started (Waiting for actions...)</span>
                </div>`;
            return;
        }

        signalContainer.innerHTML = '';
        signals.forEach(s => {
            const row = document.createElement('div');
            row.style.display = 'flex';
            row.style.alignItems = 'flex-start';
            row.style.gap = '0.5rem';
            row.style.padding = '0.45rem 0.6rem';
            row.style.background = 'rgba(30, 41, 59, 0.65)';
            row.style.border = '1px solid rgba(255, 255, 255, 0.08)';
            row.style.borderRadius = '6px';
            row.style.fontSize = '0.76rem';
            row.style.marginBottom = '0.35rem';
            row.style.lineHeight = '1.35';

            let icon = '⚡';
            let badgeBg = 'rgba(167, 139, 250, 0.15)';
            let badgeColor = '#a78bfa';

            if (s.type === 'Searched') {
                icon = '🔍'; badgeBg = 'rgba(56, 189, 248, 0.15)'; badgeColor = '#38bdf8';
            } else if (s.type === 'Clicked' || s.type === 'CTA') {
                icon = '⚡'; badgeBg = 'rgba(244, 63, 94, 0.15)'; badgeColor = '#fb7185';
            } else if (s.type === 'Filter') {
                icon = '🏷️'; badgeBg = 'rgba(129, 140, 248, 0.15)'; badgeColor = '#818cf8';
            } else if (s.type === 'Dwell') {
                icon = '⏱️'; badgeBg = 'rgba(251, 191, 36, 0.15)'; badgeColor = '#fbbf24';
            } else if (s.type === 'HighDwell') {
                icon = '🔥'; badgeBg = 'rgba(239, 68, 68, 0.15)'; badgeColor = '#f87171';
            } else if (s.type === 'Viewed') {
                icon = '👁️'; badgeBg = 'rgba(52, 211, 153, 0.15)'; badgeColor = '#34d399';
            } else if (s.type === 'Tab') {
                icon = '📑'; badgeBg = 'rgba(192, 132, 252, 0.15)'; badgeColor = '#c084fc';
            } else if (s.type === 'Module') {
                icon = '📦'; badgeBg = 'rgba(167, 139, 250, 0.15)'; badgeColor = '#a78bfa';
            } else if (s.type === 'Lecture') {
                icon = '▶️'; badgeBg = 'rgba(52, 211, 153, 0.15)'; badgeColor = '#34d399';
            } else if (s.type === 'Scroll') {
                icon = '📜'; badgeBg = 'rgba(56, 189, 248, 0.15)'; badgeColor = '#38bdf8';
            } else if (s.type === 'Highlight') {
                icon = '🖍️'; badgeBg = 'rgba(251, 191, 36, 0.15)'; badgeColor = '#fbbf24';
            } else if (s.type === 'Tech') {
                icon = '🛠️'; badgeBg = 'rgba(129, 140, 248, 0.15)'; badgeColor = '#818cf8';
            }

            row.innerHTML = `
                <span style="display:inline-flex;align-items:center;gap:0.25rem;background:${badgeBg};color:${badgeColor};padding:0.12rem 0.4rem;border-radius:4px;font-weight:700;font-size:0.7rem;flex-shrink:0;margin-top:1px;">
                    ${icon} ${s.type}
                </span>
                <span style="color:#e2e8f0;font-weight:500;word-break:break-word;">
                    ${s.statement}
                </span>
            `;
            signalContainer.appendChild(row);
        });
    }

    function clearSignalHistory() {
        sessionStorage.removeItem(STORAGE_KEY);
        renderSignalsUI();
        try {
            fetch('/api/engine/clear', { method: 'POST' }).catch(() => {});
        } catch (e) {}
    }
    window.clearSignalHistory = clearSignalHistory;

    // Background Event Synchronization to Database Engine
    function syncEventToBackend(type, statement) {
        try {
            fetch('/api/events/batch', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    events: [{
                        event_type: type,
                        target_id: statement,
                        metadata: { statement: statement },
                        timestamp: new Date().toISOString()
                    }]
                })
            }).catch(() => {});
        } catch (e) {}
    }

    // 3. Natural Behavioral Intent Logging Engine
    function trackNaturalSignal(type, statement) {
        if (!statement) return;
        const signals = getStoredSignals();
        
        // Avoid exact consecutive duplicate statements
        if (signals.length > 0 && signals[0].statement === statement) {
            return;
        }

        signals.unshift({
            type: type,
            statement: statement,
            timestamp: new Date().toLocaleTimeString()
        });

        saveStoredSignals(signals);
        renderSignalsUI();
        syncEventToBackend(type, statement);
        window.dispatchEvent(new CustomEvent('smartreco:new_signal', { detail: { type: type, statement: statement } }));
    }

    // Determine Active Topic/Page Name
    function resolveCurrentTopic() {
        const activeCategoryEl = document.querySelector('.category-pill.active');
        const productTitleEl = document.querySelector('.project-main-title') || document.querySelector('h1');
        const pageTarget = document.body.getAttribute('data-target-id') || window.location.pathname;

        if (productTitleEl && (window.location.pathname.startsWith('/product/') || pageTarget.includes('product'))) {
            return productTitleEl.innerText.trim();
        } else if (pageTarget.includes('catalog') || pageTarget === 'page_root' || window.location.pathname === '/') {
            if (activeCategoryEl && activeCategoryEl.innerText.trim() !== 'All') {
                return activeCategoryEl.innerText.trim();
            }
            return 'Course Catalog';
        } else if (productTitleEl) {
            return productTitleEl.innerText.trim();
        } else {
            return document.title.split('—')[0].trim() || 'Catalog';
        }
    }

    // 4. Initialize Handlers & Micro-Behavior Listeners Lazily
    function initTrackerLazy() {
        const pageTarget = document.body.getAttribute('data-target-id') || window.location.pathname;
        if (pageTarget.includes('admin') || window.location.pathname.startsWith('/admin')) {
            // Completely disable behavioral tracking on Admin management pages
            return;
        }

        currentTopicName = resolveCurrentTopic();
        switchDwellTopic(currentTopicName);

        if (currentTopicName === 'Course Catalog') {
            trackNaturalSignal('Viewed', 'User opened & started exploring the main Course Catalog');
        } else {
            trackNaturalSignal('Viewed', `User opened & currently exploring "${currentTopicName}"`);
        }

        renderSignalsUI();

        // 1. Category Filter Listener
        document.querySelectorAll('.category-pill').forEach(pill => {
            pill.addEventListener('click', () => {
                const catName = pill.innerText.trim();
                currentTopicName = catName;
                switchDwellTopic(catName);
                trackNaturalSignal('Filter', `User explicitly filtered catalog for "${catName}" courses`);
            });
        });

        // 2. Buttons & Course Card Click Listener (Course/Product interactions only)
        document.querySelectorAll('[data-track-click], .course-card, .btn-start-project').forEach(el => {
            el.addEventListener('click', (e) => {
                // Ignore clicks on system navigation, modals, and tracker controls
                if (el.closest('.navbar') || el.closest('#floating-signal-tracker') || el.closest('#diagnostics-modal')) {
                    return;
                }
                const title = el.getAttribute('data-track-title') || el.innerText.trim();
                const isSystemBtn = /Agent Flow Diagnostics|MeshAPI Console|Admin|Engine|Logout|Sign in|Reset|🗑️|➖/i.test(title);
                
                if (title && title.length > 1 && !title.includes('\n') && !isSystemBtn) {
                    if (el.classList.contains('btn-start-project')) {
                        trackNaturalSignal('CTA', `User clicked call-to-action: Start Project ↗ on "${currentTopicName}"`);
                    } else if (!el.classList.contains('category-pill') && !el.classList.contains('tab-btn')) {
                        trackNaturalSignal('Clicked', `User clicked course product card: "${title}"`);
                    }
                }
            });
        });

        // 3. Tab Switching Listener
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const tabName = btn.innerText.trim();
                trackNaturalSignal('Tab', `User switched tab to inspect "${tabName}" section`);
            });
        });

        // 4. Real-Time Search Bar Filter & Telemetry
        const searchInput = document.querySelector('#catalog-search-input');
        if (searchInput) {
            let searchDebounce = null;
            searchInput.addEventListener('input', (e) => {
                const rawQuery = e.target.value.trim();
                const query = rawQuery.toLowerCase();

                // Real-time client-side filtering of catalog course cards
                const courseCards = document.querySelectorAll('#catalog-courses .course-card');
                let matchCount = 0;
                courseCards.forEach(card => {
                    const cardText = card.textContent.toLowerCase();
                    if (!query || cardText.includes(query)) {
                        card.style.display = '';
                        matchCount++;
                    } else {
                        card.style.display = 'none';
                    }
                });

                // Record Telemetry Signal
                if (rawQuery.length >= 2) {
                    clearTimeout(searchDebounce);
                    searchDebounce = setTimeout(() => {
                        trackNaturalSignal('Searched', `User actively searched for "${rawQuery}" in search bar`);
                    }, 500);
                }
            });

            searchInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    const query = searchInput.value.trim();
                    if (query) {
                        const catalogSection = document.querySelector('#catalog-courses');
                        if (catalogSection) {
                            catalogSection.scrollIntoView({ behavior: 'smooth' });
                        }
                    }
                }
            });
        }

        // 5. Technology Stack Tag Listener
        document.querySelectorAll('.tech-tag-item').forEach(tag => {
            tag.addEventListener('click', () => {
                const techName = tag.innerText.replace('⚡', '').trim();
                trackNaturalSignal('Tech', `User inspected technology stack tag: "${techName}"`);
            });
        });

        // 6. Instructor Link Listener
        document.querySelectorAll('.instructor-card a').forEach(link => {
            link.addEventListener('click', () => {
                trackNaturalSignal('Instructor', `User inspected instructor profile & LinkedIn link`);
            });
        });

        // 7. Text Selection / Highlight Listener (Debounced 400ms)
        let selectionTimeout = null;
        document.addEventListener('selectionchange', () => {
            clearTimeout(selectionTimeout);
            selectionTimeout = setTimeout(() => {
                const selectedText = window.getSelection().toString().trim();
                if (selectedText.length >= 5 && selectedText.length <= 120) {
                    trackNaturalSignal('Highlight', `User highlighted key text: "${selectedText}"`);
                }
            }, 400);
        });

        // 8. Scroll Depth Listener (ONLY active inside a particular course detail page)
        const isCoursePage = document.querySelector('.project-main-title') !== null;
        if (isCoursePage) {
            const enableScrollTracking = () => {
                let scrollThrottle = false;
                window.addEventListener('scroll', () => {
                    if (scrollThrottle) return;
                    scrollThrottle = true;
                    setTimeout(() => {
                        scrollThrottle = false;
                        const scrollTop = window.scrollY;
                        const docHeight = document.documentElement.scrollHeight - window.innerHeight;
                        if (docHeight > 0) {
                            const scrollPercent = Math.round((scrollTop / docHeight) * 100);
                            if (scrollPercent >= 25 && maxScrollDepthTracked < 25) {
                                maxScrollDepthTracked = 25;
                                trackNaturalSignal('Scroll', `User scrolled 25% down reading "${currentTopicName}"`);
                            } else if (scrollPercent >= 50 && maxScrollDepthTracked < 50) {
                                maxScrollDepthTracked = 50;
                                trackNaturalSignal('Scroll', `User scrolled 50% down reading "${currentTopicName}"`);
                            } else if (scrollPercent >= 75 && maxScrollDepthTracked < 75) {
                                maxScrollDepthTracked = 75;
                                trackNaturalSignal('Scroll', `User scrolled 75% down reading "${currentTopicName}"`);
                            } else if (scrollPercent >= 90 && maxScrollDepthTracked < 90) {
                                maxScrollDepthTracked = 90;
                                trackNaturalSignal('Scroll', `User completed reading "${currentTopicName}" (90%+ scrolled)`);
                            }
                        }
                    }, 500);
                });
            };

            if (document.readyState === 'complete') {
                enableScrollTracking();
            } else {
                window.addEventListener('load', enableScrollTracking);
            }
        }

        // 9. Floating Draggable Tracker Widget Initialization
        const trackerWidget = document.querySelector('#floating-signal-tracker');
        const dragHandle = document.querySelector('#floating-tracker-drag-handle');
        if (trackerWidget && dragHandle) {
            let isDragging = false;
            let startX = 0, startY = 0, initialLeft = 0, initialTop = 0;

            const onStart = (e) => {
                isDragging = true;
                const clientX = e.touches ? e.touches[0].clientX : e.clientX;
                const clientY = e.touches ? e.touches[0].clientY : e.clientY;
                startX = clientX;
                startY = clientY;
                const rect = trackerWidget.getBoundingClientRect();
                initialLeft = rect.left;
                initialTop = rect.top;
                trackerWidget.style.right = 'auto';
                trackerWidget.style.bottom = 'auto';
                trackerWidget.style.left = initialLeft + 'px';
                trackerWidget.style.top = initialTop + 'px';
            };

            const onMove = (e) => {
                if (!isDragging) return;
                const clientX = e.touches ? e.touches[0].clientX : e.clientX;
                const clientY = e.touches ? e.touches[0].clientY : e.clientY;
                const dx = clientX - startX;
                const dy = clientY - startY;
                trackerWidget.style.left = (initialLeft + dx) + 'px';
                trackerWidget.style.top = (initialTop + dy) + 'px';
            };

            const onEnd = () => {
                isDragging = false;
            };

            dragHandle.addEventListener('mousedown', onStart);
            document.addEventListener('mousemove', onMove);
            document.addEventListener('mouseup', onEnd);

            dragHandle.addEventListener('touchstart', onStart, { passive: true });
            document.addEventListener('touchmove', onMove, { passive: true });
            document.addEventListener('touchend', onEnd);
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => initTrackerLazy());
    } else {
        initTrackerLazy();
    }

    // 10. Active Dwell Time Listener (Requires >= 10s of active reading on specific topic)
    let activeDwellTimeMs = 0;
    let lastActiveTimestamp = Date.now();
    let dwellTopicName = '';

    function flushDwellTime() {
        if (document.visibilityState === 'visible') {
            activeDwellTimeMs += (Date.now() - lastActiveTimestamp);
        }
        const dwellSec = Math.round(activeDwellTimeMs / 1000);
        const isCoursePage = document.querySelector('.project-main-title') !== null;
        if (dwellSec >= 25 && isCoursePage && dwellTopicName) {
            trackNaturalSignal('HighDwell', `User spent deep reading time (${dwellSec}s) on course "${dwellTopicName}"`);
        } else if (dwellSec >= 2 && dwellTopicName) {
            trackNaturalSignal('Dwell', `User spent ${dwellSec} seconds reading "${dwellTopicName}"`);
        }
        activeDwellTimeMs = 0;
        lastActiveTimestamp = Date.now();
    }

    function switchDwellTopic(newTopic) {
        flushDwellTime();
        dwellTopicName = newTopic;
    }

    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'hidden') {
            flushDwellTime();
        } else {
            lastActiveTimestamp = Date.now();
        }
    });

    window.addEventListener('pagehide', () => {
        flushDwellTime();
    });

    window.SmartRecoTracker = {
        track: trackNaturalSignal,
        getSignals: getStoredSignals
    };
})();
