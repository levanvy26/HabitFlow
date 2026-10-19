// -*- coding: utf-8 -*-
/**
 * HabitFlow Pro — Pure Business Logic & Mathematical Analytics Engine (R1)
 * Decoupled from React UI rendering. Loaded via <script src="js/logic.js"></script>
 * before the UI script so all helpers are available both on window and window.HabitFlowLogic.
 */
(function (global) {
  'use strict';

  // ==========================================
  // 1. DATE & CALENDAR UTILITIES (Strict Local Time)
  // ==========================================
  const DAY_NAMES_SUN_FIRST = ['CN', 'T2', 'T3', 'T4', 'T5', 'T6', 'T7'];
  const DAY_LABELS_MON_FIRST = ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN'];

  function formatLocalDate(d) {
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  function parseLocalDate(str) {
    if (!str) return new Date();
    const [y, m, d] = str.split('-').map(Number);
    return new Date(y, m - 1, d);
  }

  function formatShortDate(str) {
    if (!str) return '';
    const [, m, d] = str.split('-').map(Number);
    return `${String(d).padStart(2, '0')}/${String(m).padStart(2, '0')}`;
  }

  function getMonday(d) {
    const date = new Date(d.getFullYear(), d.getMonth(), d.getDate());
    const day = date.getDay();
    const diff = date.getDate() - day + (day === 0 ? -6 : 1);
    return new Date(date.setDate(diff));
  }

  function getWeekDates(mondayDate) {
    const dates = [];
    for (let i = 0; i < 7; i++) {
      const next = new Date(mondayDate.getFullYear(), mondayDate.getMonth(), mondayDate.getDate() + i);
      dates.push(formatLocalDate(next));
    }
    return dates;
  }

  function getDaysInMonth(year, month) {
    return new Date(year, month + 1, 0).getDate();
  }

  // ==========================================
  // 2. MONOTONE CUBIC SPLINE GENERATOR (Fritsch-Carlson)
  // ==========================================
  function buildMonotoneSplinePath(points, closedBaselineY = null) {
    if (!points || points.length === 0) return { linePath: '', areaPath: '', points: [] };

    const pts = points.map(p => {
      if (Array.isArray(p)) return { x: Number(p[0]), y: Number(p[1]) };
      if (typeof p === 'string') {
        const parts = p.split(',').map(Number);
        return { x: parts[0], y: parts[1] };
      }
      return { x: Number(p.x), y: Number(p.y) };
    }).filter(p => !isNaN(p.x) && !isNaN(p.y));

    const n = pts.length;
    if (n === 0) return { linePath: '', areaPath: '', points: [] };

    const firstX = pts[0].x.toFixed(2);
    const firstY = pts[0].y.toFixed(2);

    if (n === 1) {
      const linePath = `M ${firstX},${firstY}`;
      const areaPath = closedBaselineY !== null
        ? `M ${firstX},${closedBaselineY} L ${firstX},${firstY} L ${firstX},${closedBaselineY} Z`
        : '';
      return { linePath, areaPath, points: pts };
    }

    if (n === 2) {
      const secondX = pts[1].x.toFixed(2);
      const secondY = pts[1].y.toFixed(2);
      const linePath = `M ${firstX},${firstY} L ${secondX},${secondY}`;
      const areaPath = closedBaselineY !== null
        ? `M ${firstX},${closedBaselineY} L ${firstX},${firstY} L ${secondX},${secondY} L ${secondX},${closedBaselineY} Z`
        : '';
      return { linePath, areaPath, points: pts };
    }

    const dxs = [];
    const dys = [];
    const slopes = [];
    for (let i = 0; i < n - 1; i++) {
      const dx = pts[i + 1].x - pts[i].x;
      const dy = pts[i + 1].y - pts[i].y;
      dxs.push(dx);
      dys.push(dy);
      slopes.push(dx !== 0 ? dy / dx : 0);
    }

    const m = new Array(n).fill(0);
    m[0] = slopes[0];
    m[n - 1] = slopes[n - 2];

    for (let i = 1; i < n - 1; i++) {
      const sPrev = slopes[i - 1];
      const sCurr = slopes[i];
      if (sPrev * sCurr <= 0) {
        m[i] = 0;
      } else {
        m[i] = (sPrev + sCurr) / 2;
      }
    }

    for (let i = 0; i < n - 1; i++) {
      const s = slopes[i];
      if (s === 0) {
        m[i] = 0;
        m[i + 1] = 0;
      } else {
        let alpha = m[i] / s;
        let beta = m[i + 1] / s;
        if (alpha < 0) { m[i] = 0; alpha = 0; }
        if (beta < 0) { m[i + 1] = 0; beta = 0; }
        const distSq = alpha * alpha + beta * beta;
        if (distSq > 9) {
          const tau = 3 / Math.sqrt(distSq);
          m[i] = tau * alpha * s;
          m[i + 1] = tau * beta * s;
        }
      }
    }

    const pathCommands = [`M ${firstX},${firstY}`];
    for (let i = 0; i < n - 1; i++) {
      const p0 = pts[i];
      const p1 = pts[i + 1];
      const dx = dxs[i];
      const cp1x = (p0.x + dx / 3).toFixed(2);
      const cp1y = (p0.y + m[i] * (dx / 3)).toFixed(2);
      const cp2x = (p1.x - dx / 3).toFixed(2);
      const cp2y = (p1.y - m[i + 1] * (dx / 3)).toFixed(2);
      const x1 = p1.x.toFixed(2);
      const y1 = p1.y.toFixed(2);
      pathCommands.push(`C ${cp1x},${cp1y} ${cp2x},${cp2y} ${x1},${y1}`);
    }

    const linePath = pathCommands.join(' ');
    let areaPath = '';
    if (closedBaselineY !== null) {
      const lastX = pts[n - 1].x.toFixed(2);
      const curveBody = pathCommands.slice(1).join(' ');
      areaPath = `M ${firstX},${closedBaselineY} L ${firstX},${firstY} ${curveBody} L ${lastX},${closedBaselineY} Z`;
    }

    return { linePath, areaPath, points: pts };
  }

  // ==========================================
  // 3. FOCUS TIMER & NUMERIC LOG SCHEMA ADAPTER
  // ==========================================
  /**
   * Normalizes a single log entry (boolean | number | object | null | undefined)
   * into the canonical HabitFlow Pro numeric & Focus Timer schema:
   * { completed: boolean, focusMinutes: number, sessions: Array<{ start, end, duration, mode, note }>, note: string }
   */
  function normalizeSessionItem(s) {
    if (!s || typeof s !== 'object') return null;
    const duration = Math.max(0, Number(s.duration) || 0);
    return {
      start: s.start || null,
      end: s.end || null,
      duration,
      mode: s.mode === 'stopwatch' ? 'stopwatch' : 'pomodoro',
      note: typeof s.note === 'string' ? s.note : ''
    };
  }

  function normalizeLogEntry(entry) {
    if (entry === null || entry === undefined) {
      return { completed: false, focusMinutes: 0, sessions: [], note: '' };
    }
    if (typeof entry === 'boolean') {
      return { completed: entry, focusMinutes: 0, sessions: [], note: '' };
    }
    if (typeof entry === 'number') {
      const mins = Math.max(0, Number(entry) || 0);
      return { completed: mins > 0, focusMinutes: mins, sessions: [], note: '' };
    }
    if (typeof entry === 'object') {
      const sessions = Array.isArray(entry.sessions)
        ? entry.sessions.map(normalizeSessionItem).filter(Boolean)
        : [];
      const sessionSum = sessions.reduce((acc, s) => acc + (Number(s.duration) || 0), 0);
      const rawFocus = Number(entry.focusMinutes);
      const focusMinutes = !isNaN(rawFocus) && rawFocus >= 0
        ? Math.max(rawFocus, sessionSum)
        : sessionSum;
      const note = typeof entry.note === 'string' ? entry.note : '';
      return {
        completed: Boolean(entry.completed),
        focusMinutes: Math.round(focusMinutes * 100) / 100,
        sessions,
        note
      };
    }
    return { completed: Boolean(entry), focusMinutes: 0, sessions: [], note: '' };
  }

  /**
   * Adapter: Normalizes an entire logs map { [dateStr]: { [habitId]: boolean | object } }
   * into the canonical object schema while remaining 100% backward-compatible.
   */
  function normalizeLogsMap(logs) {
    if (!logs || typeof logs !== 'object') return {};
    const normalized = {};
    for (const [dateStr, dayMap] of Object.entries(logs)) {
      if (!dayMap || typeof dayMap !== 'object') continue;
      normalized[dateStr] = {};
      for (const [habitId, entry] of Object.entries(dayMap)) {
        normalized[dateStr][habitId] = normalizeLogEntry(entry);
      }
    }
    return normalized;
  }

  /**
   * Backward-compatible completion check for both legacy boolean logs and object logs.
   * Prevents `{ completed: false, focusMinutes: 10 }` from being treated as truthy completed.
   */
  function isLogCompleted(entry) {
    if (!entry) return false;
    if (typeof entry === 'boolean') return entry;
    if (typeof entry === 'number') return entry > 0;
    if (typeof entry === 'object') return Boolean(entry.completed);
    return Boolean(entry);
  }

  function getLogFocusMinutes(entry) {
    if (!entry || typeof entry !== 'object') return 0;
    return normalizeLogEntry(entry).focusMinutes;
  }

  function getLogSessions(entry) {
    if (!entry || typeof entry !== 'object') return [];
    return normalizeLogEntry(entry).sessions;
  }

  function getLogNote(entry) {
    if (!entry || typeof entry !== 'object') return '';
    return typeof entry.note === 'string' ? entry.note : '';
  }

  /**
   * Pure immutable helper for toggling a habit's completion state on a given date
   * while preserving any recorded Focus Timer minutes, sessions, and notes.
   */
  function toggleHabitLogEntry(logs, dateStr, habitId) {
    const safeLogs = logs || {};
    const currentDayLogs = { ...(safeLogs[dateStr] || {}) };
    const existingRaw = currentDayLogs[habitId];
    const existing = normalizeLogEntry(existingRaw);
    const nextCompleted = !existing.completed;
    const hasFocusData = existing.focusMinutes > 0 || existing.sessions.length > 0 || Boolean(existing.note);

    if (!nextCompleted && !hasFocusData) {
      delete currentDayLogs[habitId];
    } else {
      currentDayLogs[habitId] = {
        completed: nextCompleted,
        focusMinutes: existing.focusMinutes,
        sessions: existing.sessions,
        ...(existing.note ? { note: existing.note } : {})
      };
    }

    return {
      ...safeLogs,
      [dateStr]: currentDayLogs
    };
  }

  /**
   * Pure immutable helper to record a Focus Timer session into logs[dateStr][habit.id].
   * Automatically marks `completed = true` if cumulative `focusMinutes >= habit.targetMinutes` (when targetMinutes > 0).
   */
  function recordFocusSession(logs, dateStr, habit, sessionInput) {
    const safeLogs = logs || {};
    const habitId = typeof habit === 'string' ? habit : habit?.id;
    if (!habitId || !dateStr) return safeLogs;

    const targetMinutes = typeof habit === 'object' ? (Number(habit?.targetMinutes) || 0) : 0;
    const currentDayLogs = { ...(safeLogs[dateStr] || {}) };
    const existing = normalizeLogEntry(currentDayLogs[habitId]);

    const duration = Math.max(0, Math.round((Number(sessionInput?.duration) || 0) * 100) / 100);
    const cleanNote = typeof sessionInput?.note === 'string' ? sessionInput.note.trim() : '';
    const newSession = normalizeSessionItem({
      start: sessionInput?.start || new Date().toISOString(),
      end: sessionInput?.end || new Date().toISOString(),
      duration,
      mode: sessionInput?.mode === 'stopwatch' ? 'stopwatch' : 'pomodoro',
      note: cleanNote
    });

    const updatedSessions = newSession && duration > 0
      ? [...existing.sessions, newSession]
      : existing.sessions;

    const totalFocusMinutes = Math.round((existing.focusMinutes + duration) * 100) / 100;
    const autoCompleted = targetMinutes > 0 && totalFocusMinutes >= targetMinutes;
    const finalCompleted = Boolean(existing.completed || autoCompleted || sessionInput?.markCompleted);
    const finalNote = cleanNote || existing.note || '';

    currentDayLogs[habitId] = {
      completed: finalCompleted,
      focusMinutes: totalFocusMinutes,
      sessions: updatedSessions,
      ...(finalNote ? { note: finalNote } : {})
    };

    return {
      ...safeLogs,
      [dateStr]: currentDayLogs
    };
  }

  /**
   * Anti-throttling elapsed time calculator based on wall-clock timestamp delta:
   * elapsed = accumulatedMs + (nowMs - startTimeMs)
   */
  function computeTimerElapsedMs(startTimeMs, nowMs = Date.now(), accumulatedMs = 0) {
    const base = Math.max(0, Number(accumulatedMs) || 0);
    if (typeof startTimeMs === 'number' && startTimeMs > 0 && nowMs >= startTimeMs) {
      return Math.floor(base + (nowMs - startTimeMs));
    }
    return Math.floor(base);
  }

  /**
   * Formats focus duration in minutes into a concise string (e.g., "25m", "1h 30m", "2h").
   */
  function formatFocusDuration(minutes, options = {}) {
    const raw = Math.max(0, Number(minutes) || 0);
    const totalMinutes = Math.round(raw);
    const hrs = Math.floor(totalMinutes / 60);
    const mins = totalMinutes % 60;

    if (options.compact === false) {
      if (hrs > 0 && mins > 0) return `${hrs} giờ ${mins} phút`;
      if (hrs > 0) return `${hrs} giờ`;
      return `${mins} phút`;
    }

    if (hrs > 0 && mins > 0) {
      return `${hrs}h ${String(mins).padStart(2, '0')}m`;
    }
    if (hrs > 0) {
      return `${hrs}h`;
    }
    return `${mins}m`;
  }

  /**
   * Formats milliseconds (or seconds) into digital clock string "MM:SS" or "HH:MM:SS".
   */
  function formatTimerClock(value, isMilliseconds = true) {
    const totalSeconds = Math.max(0, Math.floor((Number(value) || 0) / (isMilliseconds ? 1000 : 1)));
    const hrs = Math.floor(totalSeconds / 3600);
    const mins = Math.floor((totalSeconds % 3600) / 60);
    const secs = totalSeconds % 60;
    if (hrs > 0) {
      return `${String(hrs).padStart(2, '0')}:${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
    }
    return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  }

  /**
   * Pure helper: Calculates total Focus Timer minutes across logs with optional filters:
   * options: { dateStr, startDate, endDate, habitId } (or string habitId as 2nd parameter).
   */
  function computeTotalFocusMinutes(logs, options = {}) {
    if (!logs || typeof logs !== 'object') return 0;
    const opts = typeof options === 'string' ? { habitId: options } : (options || {});
    const { dateStr, startDate, endDate, habitId } = opts;

    let total = 0;

    if (dateStr) {
      const dayMap = logs[dateStr];
      if (!dayMap || typeof dayMap !== 'object') return 0;
      if (habitId) {
        return getLogFocusMinutes(dayMap[habitId]);
      }
      for (const entry of Object.values(dayMap)) {
        total += getLogFocusMinutes(entry);
      }
      return Math.round(total * 100) / 100;
    }

    for (const [dStr, dayMap] of Object.entries(logs)) {
      if (!dayMap || typeof dayMap !== 'object') continue;
      if (startDate && dStr < startDate) continue;
      if (endDate && dStr > endDate) continue;

      if (habitId) {
        total += getLogFocusMinutes(dayMap[habitId]);
      } else {
        for (const entry of Object.values(dayMap)) {
          total += getLogFocusMinutes(entry);
        }
      }
    }

    return Math.round(total * 100) / 100;
  }

  /**
   * Pure helper: Computes Focus Timer allocation by category across a date range or all logs.
   * Returns sorted array: [{ category, color, icon, focusMinutes, sessionCount, percentage }]
   */
  function computeCategoryFocusAllocation(habits, logs, categories = [], options = {}) {
    const safeHabits = Array.isArray(habits) ? habits : [];
    const safeLogs = logs || {};
    const safeCategories = Array.isArray(categories) ? categories : [];
    const { dateStr, startDate, endDate } = options || {};

    const habitMap = {};
    for (const h of safeHabits) {
      if (h && h.id) habitMap[h.id] = h;
    }

    const catMetaMap = {};
    for (const c of safeCategories) {
      if (c && c.name) {
        catMetaMap[c.name] = {
          color: c.color || '#6366F1',
          icon: c.icon || 'layers'
        };
      }
    }

    const buckets = {};
    for (const h of safeHabits) {
      const catName = h.category || 'Chưa phân loại';
      if (!buckets[catName]) {
        const meta = catMetaMap[catName] || { color: h.color || '#6366F1', icon: h.icon || 'layers' };
        buckets[catName] = {
          category: catName,
          color: meta.color,
          icon: meta.icon,
          focusMinutes: 0,
          sessionCount: 0
        };
      }
    }

    for (const [dStr, dayMap] of Object.entries(safeLogs)) {
      if (!dayMap || typeof dayMap !== 'object') continue;
      if (dateStr && dStr !== dateStr) continue;
      if (startDate && dStr < startDate) continue;
      if (endDate && dStr > endDate) continue;

      for (const [hid, rawEntry] of Object.entries(dayMap)) {
        const norm = normalizeLogEntry(rawEntry);
        if (norm.focusMinutes <= 0 && norm.sessions.length === 0) continue;
        const h = habitMap[hid];
        const catName = h?.category || 'Chưa phân loại';
        if (!buckets[catName]) {
          const meta = catMetaMap[catName] || { color: h?.color || '#6366F1', icon: h?.icon || 'layers' };
          buckets[catName] = {
            category: catName,
            color: meta.color,
            icon: meta.icon,
            focusMinutes: 0,
            sessionCount: 0
          };
        }
        buckets[catName].focusMinutes = Math.round((buckets[catName].focusMinutes + norm.focusMinutes) * 100) / 100;
        buckets[catName].sessionCount += norm.sessions.length;
      }
    }

    const list = Object.values(buckets);
    const grandTotal = list.reduce((acc, item) => acc + item.focusMinutes, 0);

    return list
      .map(item => ({
        ...item,
        percentage: grandTotal > 0 ? Math.round((item.focusMinutes / grandTotal) * 1000) / 10 : 0
      }))
      .sort((a, b) => b.focusMinutes - a.focusMinutes);
  }

  // ==========================================
  // 3B. STREAK & RECORD STREAK ENGINE
  // ==========================================
  function calculateStreak(habitId, logs, todayStr) {
    if (!logs) return 0;
    let streak = 0;
    const today = parseLocalDate(todayStr);

    const isTodayCompleted = isLogCompleted(logs[todayStr]?.[habitId]);
    const checkDate = new Date(today);

    if (!isTodayCompleted) {
      checkDate.setDate(checkDate.getDate() - 1);
      const yesterdayStr = formatLocalDate(checkDate);
      if (!isLogCompleted(logs[yesterdayStr]?.[habitId])) {
        return 0;
      }
    }

    while (true) {
      const dStr = formatLocalDate(checkDate);
      if (isLogCompleted(logs[dStr]?.[habitId])) {
        streak++;
        checkDate.setDate(checkDate.getDate() - 1);
      } else {
        break;
      }
    }

    return streak;
  }

  function calculateRecordStreak(habitId, logs) {
    if (!habitId || !logs || typeof logs !== 'object') return 0;

    const completedDates = [];
    const dateKeys = Object.keys(logs);
    for (let i = 0; i < dateKeys.length; i++) {
      const dateStr = dateKeys[i];
      if (isLogCompleted(logs[dateStr]?.[habitId])) {
        completedDates.push(dateStr);
      }
    }

    if (completedDates.length === 0) return 0;
    if (completedDates.length === 1) return 1;

    completedDates.sort();

    let maxStreak = 1;
    let currentStreak = 1;

    for (let i = 1; i < completedDates.length; i++) {
      const prevDateStr = completedDates[i - 1];
      const currDateStr = completedDates[i];

      const [y, m, d] = prevDateStr.split('-').map(Number);
      const nextCalendarDate = new Date(Date.UTC(y, m - 1, d + 1));
      const expectedNextStr = nextCalendarDate.toISOString().slice(0, 10);

      if (currDateStr === expectedNextStr) {
        currentStreak++;
        if (currentStreak > maxStreak) {
          maxStreak = currentStreak;
        }
      } else if (currDateStr === prevDateStr) {
        continue;
      } else {
        currentStreak = 1;
      }
    }
    return maxStreak;
  }

  // ==========================================
  // 4. SYSTEM CATEGORY HELPERS
  // ==========================================
  const SYSTEM_CATEGORY_IDS = new Set(['cat-all', 'cat-uncategorized']);
  const SYSTEM_CATEGORY_NAMES = new Set(['Tất cả', 'Chưa phân loại']);

  function isDefaultCategory(cat) {
    if (!cat) return true;
    if (cat.id && SYSTEM_CATEGORY_IDS.has(cat.id)) return true;
    if (cat.name && SYSTEM_CATEGORY_NAMES.has(cat.name.trim())) return true;
    return false;
  }

  // ==========================================
  // 5. UNIFIED PERIOD COMPARISON & KPI ENGINE
  // ==========================================
  /**
   * Shared mathematical comparison between current and previous period actuals/possibles.
   * Used by both Dashboard KPIs and HabitGrowthModal (Week, Month, Year).
   */
  function comparePeriod(thisActual, thisPossible, lastActual, lastPossible) {
    const currentRate = thisPossible > 0 ? (thisActual / thisPossible) * 100 : 0;
    const lastRate = lastPossible > 0 ? (lastActual / lastPossible) * 100 : 0;
    const deltaRate = currentRate - lastRate;
    const deltaAbs = thisActual - lastActual;
    const pctChange = lastActual > 0 ? ((thisActual - lastActual) / lastActual) * 100 : null;
    const trend = deltaAbs > 0 ? 'tăng' : deltaAbs < 0 ? 'giảm' : 'ổn định';
    return {
      currentRate,
      lastRate,
      deltaRate,
      deltaAbs,
      pctChange,
      trend
    };
  }

  function computeHabitStreaksMap(habits, logs, todayStr) {
    const safeHabits = habits || [];
    const safeLogs = logs || {};
    const map = {};
    for (const h of safeHabits) {
      map[h.id] = {
        current: calculateStreak(h.id, safeLogs, todayStr),
        record: calculateRecordStreak(h.id, safeLogs)
      };
    }
    return map;
  }

  function computeDashboardKpis(habits, logs, todayStr, precomputedStreaksMap) {
    const safeHabits = habits || [];
    const safeLogs = logs || {};
    const totalHabits = safeHabits.length;

    if (totalHabits === 0) {
      return {
        longestStreak: { streak: 0, habitName: 'Chưa có', record: 0 },
        weekRate: { current: 0, delta: 0, last: 0, elapsedText: 'T2 - T4' },
        monthRate: { current: 0, delta: 0, last: 0, elapsedDays: 1 },
        yearRate: { current: 0, delta: 0, last: 0, elapsedDays: 1 }
      };
    }

    const streaksMap = precomputedStreaksMap || computeHabitStreaksMap(safeHabits, safeLogs, todayStr);

    // 1. Longest Current Streak & All-Time Record
    let maxCurrentStreak = 0;
    let leadingHabitName = safeHabits[0]?.name || 'Chưa có';
    let allTimeRecord = 0;

    for (const h of safeHabits) {
      const entry = streaksMap[h.id] || {
        current: calculateStreak(h.id, safeLogs, todayStr),
        record: calculateRecordStreak(h.id, safeLogs)
      };
      if (entry.current > maxCurrentStreak) {
        maxCurrentStreak = entry.current;
        leadingHabitName = h.name;
      }
      if (entry.record > allTimeRecord) {
        allTimeRecord = entry.record;
      }
    }

    // 2. This Week vs Last Week (Elapsed days)
    const todayDate = parseLocalDate(todayStr);
    const thisMon = getMonday(todayDate);
    const lastMon = new Date(thisMon.getFullYear(), thisMon.getMonth(), thisMon.getDate() - 7);
    const currentDayOfWeek = todayDate.getDay();
    const elapsedDaysInWeek = currentDayOfWeek === 0 ? 7 : currentDayOfWeek;

    let thisWeekActual = 0;
    let lastWeekActual = 0;
    for (let i = 0; i < elapsedDaysInWeek; i++) {
      const sThis = formatLocalDate(new Date(thisMon.getFullYear(), thisMon.getMonth(), thisMon.getDate() + i));
      const sLast = formatLocalDate(new Date(lastMon.getFullYear(), lastMon.getMonth(), lastMon.getDate() + i));
      for (const h of safeHabits) {
        if (isLogCompleted(safeLogs[sThis]?.[h.id])) thisWeekActual++;
        if (isLogCompleted(safeLogs[sLast]?.[h.id])) lastWeekActual++;
      }
    }

    const thisWeekPossible = totalHabits * elapsedDaysInWeek;
    const weekComp = comparePeriod(thisWeekActual, thisWeekPossible, lastWeekActual, thisWeekPossible);
    const elapsedWeekText = `T2 - ${DAY_NAMES_SUN_FIRST[currentDayOfWeek]}`;

    // 3. This Month vs Last Month (First N elapsed days)
    const currentYear = todayDate.getFullYear();
    const currentMonth = todayDate.getMonth();
    const currentDayOfMonth = todayDate.getDate();

    const prevMonthDate = new Date(currentYear, currentMonth - 1, 1);
    const prevYear = prevMonthDate.getFullYear();
    const prevMonth = prevMonthDate.getMonth();
    const daysInPrevMonth = getDaysInMonth(prevYear, prevMonth);
    const compareDaysMonth = Math.min(currentDayOfMonth, daysInPrevMonth);

    let thisMonthActual = 0;
    let lastMonthActual = 0;
    for (let d = 1; d <= currentDayOfMonth; d++) {
      const sThis = `${currentYear}-${String(currentMonth + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
      for (const h of safeHabits) {
        if (isLogCompleted(safeLogs[sThis]?.[h.id])) thisMonthActual++;
      }
    }
    for (let d = 1; d <= compareDaysMonth; d++) {
      const sLast = `${prevYear}-${String(prevMonth + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
      for (const h of safeHabits) {
        if (isLogCompleted(safeLogs[sLast]?.[h.id])) lastMonthActual++;
      }
    }

    const monthComp = comparePeriod(
      thisMonthActual,
      totalHabits * currentDayOfMonth,
      lastMonthActual,
      totalHabits * compareDaysMonth
    );

    // 4. This Year vs Last Year (Same elapsed days in year)
    const startOfThisYear = new Date(currentYear, 0, 1);
    const dayOfYear = Math.floor((todayDate - startOfThisYear) / (24 * 3600 * 1000)) + 1;

    let thisYearActual = 0;
    let lastYearActual = 0;
    for (let i = 0; i < dayOfYear; i++) {
      const sThis = formatLocalDate(new Date(currentYear, 0, 1 + i));
      const sLast = formatLocalDate(new Date(currentYear - 1, 0, 1 + i));
      for (const h of safeHabits) {
        if (isLogCompleted(safeLogs[sThis]?.[h.id])) thisYearActual++;
        if (isLogCompleted(safeLogs[sLast]?.[h.id])) lastYearActual++;
      }
    }

    const yearPossible = totalHabits * dayOfYear;
    const yearComp = comparePeriod(thisYearActual, yearPossible, lastYearActual, yearPossible);

    return {
      longestStreak: {
        streak: maxCurrentStreak,
        habitName: leadingHabitName,
        record: allTimeRecord
      },
      weekRate: {
        current: weekComp.currentRate,
        last: weekComp.lastRate,
        delta: weekComp.deltaRate,
        elapsedText: elapsedWeekText
      },
      monthRate: {
        current: monthComp.currentRate,
        last: monthComp.lastRate,
        delta: monthComp.deltaRate,
        elapsedDays: currentDayOfMonth
      },
      yearRate: {
        current: yearComp.currentRate,
        last: yearComp.lastRate,
        delta: yearComp.deltaRate,
        elapsedDays: dayOfYear
      }
    };
  }

  function computeWeekDaySummaries(habits, logs, currentWeekDates) {
    const safeHabits = habits || [];
    const safeLogs = logs || {};
    return (currentWeekDates || []).map(dStr => {
      let count = 0;
      for (const h of safeHabits) {
        if (isLogCompleted(safeLogs[dStr]?.[h.id])) count++;
      }
      const pct = safeHabits.length > 0 ? Math.round((count / safeHabits.length) * 100) : 0;
      return { date: dStr, count, total: safeHabits.length, pct };
    });
  }

  // ==========================================
  // 6. HABIT GROWTH MODAL ANALYTICS ENGINES
  // ==========================================
  function computeHabitWeekAnalytics(habitId, logs, todayStr) {
    const safeLogs = logs || {};
    const todayDate = parseLocalDate(todayStr);
    const currentDayOfWeek = todayDate.getDay();
    const elapsedDaysInWeek = currentDayOfWeek === 0 ? 7 : currentDayOfWeek;
    const thisMon = getMonday(todayDate);
    const lastMon = new Date(thisMon.getFullYear(), thisMon.getMonth(), thisMon.getDate() - 7);

    const days = DAY_LABELS_MON_FIRST.map((lbl, i) => {
      const dThis = new Date(thisMon.getFullYear(), thisMon.getMonth(), thisMon.getDate() + i);
      const dLast = new Date(lastMon.getFullYear(), lastMon.getMonth(), lastMon.getDate() + i);
      const sThis = formatLocalDate(dThis);
      const sLast = formatLocalDate(dLast);

      const isFuture = i >= elapsedDaysInWeek;
      const isToday = sThis === todayStr;

      const doneThis = isFuture ? null : isLogCompleted(safeLogs[sThis]?.[habitId]);
      const doneLast = isLogCompleted(safeLogs[sLast]?.[habitId]);

      return {
        label: lbl,
        dateThis: sThis,
        dateLast: sLast,
        isFuture,
        isToday,
        doneThis,
        doneLast
      };
    });

    let thisWeekActual = 0;
    let lastWeekElapsedActual = 0;
    let lastWeekFullActual = 0;

    days.forEach(d => {
      if (d.doneLast) lastWeekFullActual++;
      if (!d.isFuture) {
        if (d.doneThis) thisWeekActual++;
        if (d.doneLast) lastWeekElapsedActual++;
      }
    });

    const comp = comparePeriod(thisWeekActual, elapsedDaysInWeek, lastWeekElapsedActual, elapsedDaysInWeek);
    const { currentRate: thisWeekRate, lastRate: lastWeekRate, deltaRate, deltaAbs, pctChange, trend } = comp;

    let comment = '';
    if (lastWeekElapsedActual === 0 && thisWeekActual === 0) {
      comment = 'Chưa ghi nhận hoàn thành trong cả tuần này và cùng kỳ tuần trước.';
    } else if (lastWeekElapsedActual === 0) {
      comment = `Kỳ trước đạt 0 ngày. Tuần này hoàn thành ${thisWeekActual}/${elapsedDaysInWeek} ngày (${thisWeekRate.toFixed(0)}%).`;
    } else if (deltaAbs > 0) {
      comment = `Tiến bộ tích cực: tăng +${deltaAbs} ngày hoàn thành (+${pctChange.toFixed(1)}%) so với cùng kỳ tuần trước.`;
    } else if (deltaAbs < 0) {
      comment = `Sụt giảm ${Math.abs(deltaAbs)} ngày (${pctChange.toFixed(1)}%) so với cùng khoảng thời gian tuần trước.`;
    } else {
      comment = `Duy trì phong độ ổn định (${thisWeekActual}/${elapsedDaysInWeek} ngày) tương đương tuần trước.`;
    }

    return {
      days,
      elapsedDays: elapsedDaysInWeek,
      thisWeekActual,
      lastWeekElapsedActual,
      lastWeekFullActual,
      thisWeekRate,
      lastWeekRate,
      deltaRate,
      deltaAbs,
      pctChange,
      trend,
      comment,
      timeframe: `T2 - ${DAY_NAMES_SUN_FIRST[currentDayOfWeek]} (${elapsedDaysInWeek} ngày)`
    };
  }

  function computeHabitMonthAnalytics(habitId, logs, todayStr) {
    const safeLogs = logs || {};
    const todayDate = parseLocalDate(todayStr);
    const currentYear = todayDate.getFullYear();
    const currentMonth = todayDate.getMonth();
    const currentDayOfMonth = todayDate.getDate();

    const daysInThisMonth = getDaysInMonth(currentYear, currentMonth);
    const prevMonthDate = new Date(currentYear, currentMonth - 1, 1);
    const prevYear = prevMonthDate.getFullYear();
    const prevMonth = prevMonthDate.getMonth();
    const daysInPrevMonth = getDaysInMonth(prevYear, prevMonth);

    const compareDaysMonth = Math.min(currentDayOfMonth, daysInPrevMonth);

    let cumThis = 0;
    let cumLast = 0;
    const maxDays = Math.max(daysInThisMonth, daysInPrevMonth);
    const days = [];

    for (let d = 1; d <= maxDays; d++) {
      const isThisValid = d <= daysInThisMonth;
      const isLastValid = d <= daysInPrevMonth;
      const isFuture = d > currentDayOfMonth;

      const sThis = isThisValid ? `${currentYear}-${String(currentMonth + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}` : null;
      const sLast = isLastValid ? `${prevYear}-${String(prevMonth + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}` : null;

      let doneThis = null;
      if (isThisValid && !isFuture) {
        doneThis = isLogCompleted(safeLogs[sThis]?.[habitId]);
        if (doneThis) cumThis++;
      }

      let doneLast = null;
      if (isLastValid) {
        doneLast = isLogCompleted(safeLogs[sLast]?.[habitId]);
        if (doneLast) cumLast++;
      }

      days.push({
        day: d,
        isThisValid,
        isLastValid,
        isFuture,
        sThis,
        sLast,
        doneThis,
        doneLast,
        cumThis: !isFuture && isThisValid ? cumThis : null,
        cumLast: isLastValid ? cumLast : null
      });
    }

    let thisMonthActual = 0;
    let lastMonthElapsedActual = 0;
    let lastMonthFullActual = 0;

    for (let d = 1; d <= currentDayOfMonth; d++) {
      const s = `${currentYear}-${String(currentMonth + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
      if (isLogCompleted(safeLogs[s]?.[habitId])) thisMonthActual++;
    }
    for (let d = 1; d <= compareDaysMonth; d++) {
      const s = `${prevYear}-${String(prevMonth + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
      if (isLogCompleted(safeLogs[s]?.[habitId])) lastMonthElapsedActual++;
    }
    for (let d = 1; d <= daysInPrevMonth; d++) {
      const s = `${prevYear}-${String(prevMonth + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
      if (isLogCompleted(safeLogs[s]?.[habitId])) lastMonthFullActual++;
    }

    const comp = comparePeriod(thisMonthActual, currentDayOfMonth, lastMonthElapsedActual, compareDaysMonth);
    const { currentRate: thisMonthRate, lastRate: lastMonthRate, deltaRate, deltaAbs, pctChange, trend } = comp;

    let comment = '';
    if (lastMonthElapsedActual === 0 && thisMonthActual === 0) {
      comment = 'Chưa ghi nhận hoàn thành trong khoảng ngày đối chiếu ở cả hai tháng.';
    } else if (lastMonthElapsedActual === 0) {
      comment = `Kỳ trước bằng 0. Tháng này đạt ${thisMonthActual}/${currentDayOfMonth} ngày (${thisMonthRate.toFixed(0)}%).`;
    } else if (deltaAbs > 0) {
      comment = `Tăng trưởng +${deltaAbs} ngày hoàn thành (+${pctChange.toFixed(1)}%) so với cùng ${compareDaysMonth} ngày đầu tháng trước.`;
    } else if (deltaAbs < 0) {
      comment = `Giảm ${Math.abs(deltaAbs)} ngày (${pctChange.toFixed(1)}%) so với cùng kỳ tháng trước.`;
    } else {
      comment = `Phong độ ổn định, hoàn thành ${thisMonthActual}/${currentDayOfMonth} ngày tương đương tháng trước.`;
    }

    return {
      days,
      maxDays,
      currentDayOfMonth,
      compareDaysMonth,
      thisMonthNum: currentMonth + 1,
      prevMonthNum: prevMonth + 1,
      thisMonthActual,
      lastMonthElapsedActual,
      lastMonthFullActual,
      thisMonthRate,
      lastMonthRate,
      deltaRate,
      deltaAbs,
      pctChange,
      trend,
      comment,
      timeframe: `Ngày 01/${currentMonth + 1} - ${String(currentDayOfMonth).padStart(2, '0')}/${currentMonth + 1} (${currentDayOfMonth} ngày)`
    };
  }

  function computeHabitYearAnalytics(habitId, logs, todayStr) {
    const safeLogs = logs || {};
    const todayDate = parseLocalDate(todayStr);
    const currentYear = todayDate.getFullYear();
    const currentMonth = todayDate.getMonth();
    const currentDayOfMonth = todayDate.getDate();
    const prevYear = currentYear - 1;
    const startOfThisYear = new Date(currentYear, 0, 1);
    const dayOfYear = Math.floor((todayDate - startOfThisYear) / (24 * 3600 * 1000)) + 1;

    const months = Array.from({ length: 12 }, (_, i) => i);
    const monthData = months.map(m => {
      const dimThis = getDaysInMonth(currentYear, m);
      const dimLast = getDaysInMonth(prevYear, m);

      const isFuture = m > currentMonth;
      const isCurrent = m === currentMonth;

      let activeDaysThis = dimThis;
      if (isCurrent) activeDaysThis = currentDayOfMonth;
      else if (isFuture) activeDaysThis = 0;

      let activeDaysLast = dimLast;
      if (isCurrent) activeDaysLast = Math.min(currentDayOfMonth, dimLast);
      else if (isFuture) activeDaysLast = 0;

      let countThis = 0;
      if (activeDaysThis > 0) {
        for (let d = 1; d <= activeDaysThis; d++) {
          const s = `${currentYear}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
          if (isLogCompleted(safeLogs[s]?.[habitId])) countThis++;
        }
      }

      let countLast = 0;
      if (activeDaysLast > 0) {
        for (let d = 1; d <= activeDaysLast; d++) {
          const s = `${prevYear}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
          if (isLogCompleted(safeLogs[s]?.[habitId])) countLast++;
        }
      }

      let countLastFull = 0;
      for (let d = 1; d <= dimLast; d++) {
        const s = `${prevYear}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
        if (isLogCompleted(safeLogs[s]?.[habitId])) countLastFull++;
      }

      const rateThis = activeDaysThis > 0 ? (countThis / activeDaysThis) * 100 : 0;
      const rateLast = activeDaysLast > 0 ? (countLast / activeDaysLast) * 100 : 0;
      const rateLastFull = (countLastFull / dimLast) * 100;

      return {
        month: m + 1,
        isFuture,
        isCurrent,
        activeDaysThis,
        activeDaysLast,
        countThis,
        countLast,
        countLastFull,
        rateThis,
        rateLast,
        rateLastFull,
        dimThis,
        dimLast
      };
    });

    let thisYearActual = 0;
    let lastYearElapsedActual = 0;

    for (let i = 0; i < dayOfYear; i++) {
      const sThis = formatLocalDate(new Date(currentYear, 0, 1 + i));
      const sLast = formatLocalDate(new Date(prevYear, 0, 1 + i));
      if (isLogCompleted(safeLogs[sThis]?.[habitId])) thisYearActual++;
      if (isLogCompleted(safeLogs[sLast]?.[habitId])) lastYearElapsedActual++;
    }

    const comp = comparePeriod(thisYearActual, dayOfYear, lastYearElapsedActual, dayOfYear);
    const { currentRate: thisYearRate, lastRate: lastYearRate, deltaRate, deltaAbs, pctChange, trend } = comp;

    let comment = '';
    if (lastYearElapsedActual === 0 && thisYearActual === 0) {
      comment = 'Chưa ghi nhận hoàn thành nào trong năm nay và năm trước.';
    } else if (lastYearElapsedActual === 0) {
      comment = `Năm trước ghi nhận 0 lượt hoàn thành. Năm nay đã đạt ${thisYearActual}/${dayOfYear} ngày (${thisYearRate.toFixed(1)}%).`;
    } else if (deltaAbs > 0) {
      comment = `Tiến độ năm ${currentYear} tăng +${deltaAbs} ngày (+${pctChange.toFixed(1)}%) so với cùng ${dayOfYear} ngày năm ${prevYear}.`;
    } else if (deltaAbs < 0) {
      comment = `Tiến độ năm ${currentYear} sụt giảm ${Math.abs(deltaAbs)} ngày (${pctChange.toFixed(1)}%) so với cùng kỳ năm ${prevYear}.`;
    } else {
      comment = `Phong độ duy trì tương đồng (${thisYearActual}/${dayOfYear} ngày) giữa năm ${currentYear} và năm ${prevYear}.`;
    }

    return {
      monthData,
      currentYear,
      prevYear,
      dayOfYear,
      thisYearActual,
      lastYearElapsedActual,
      thisYearRate,
      lastYearRate,
      deltaRate,
      deltaAbs,
      pctChange,
      trend,
      comment,
      timeframe: `01/01 - ${String(currentDayOfMonth).padStart(2, '0')}/${currentMonth + 1} (${dayOfYear} ngày)`
    };
  }

  const HabitFlowLogic = {
    DAY_NAMES_SUN_FIRST,
    DAY_LABELS_MON_FIRST,
    formatLocalDate,
    parseLocalDate,
    formatShortDate,
    getMonday,
    getWeekDates,
    getDaysInMonth,
    buildMonotoneSplinePath,
    normalizeSessionItem,
    normalizeLogEntry,
    normalizeLogsMap,
    isLogCompleted,
    getLogFocusMinutes,
    getLogSessions,
    getLogNote,
    toggleHabitLogEntry,
    recordFocusSession,
    computeTimerElapsedMs,
    formatFocusDuration,
    formatTimerClock,
    computeTotalFocusMinutes,
    computeCategoryFocusAllocation,
    calculateStreak,
    calculateRecordStreak,
    SYSTEM_CATEGORY_IDS,
    SYSTEM_CATEGORY_NAMES,
    isDefaultCategory,
    comparePeriod,
    computeHabitStreaksMap,
    computeDashboardKpis,
    computeWeekDaySummaries,
    computeHabitWeekAnalytics,
    computeHabitMonthAnalytics,
    computeHabitYearAnalytics
  };

  // Export both to window.HabitFlowLogic and top-level global scope for seamless compatibility
  global.HabitFlowLogic = HabitFlowLogic;
  Object.assign(global, HabitFlowLogic);
})(typeof window !== 'undefined' ? window : globalThis);


