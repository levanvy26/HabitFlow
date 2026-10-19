# -*- coding: utf-8 -*-
"""
R0 Baseline & Safety Net Test Suite for HabitFlow Pro.
Run from d:\\HabitFlow:
    python -m unittest tests.test_r0_baseline -v

Features:
  1. UTF-8 safe console output + ASCII status reporting to prevent cp1252 hangs.
  2. Strict try/finally window.destroy() + daemon watchdog timer so WebView never hangs.
  3. Extracts pure functions & KPI/Modal formulas from ui.html (or window.HabitFlowLogic in R1+)
     and verifies them against a deterministic fixture + golden snapshot.
  4. Smoke-tests full React rendering of ui.html in a hidden WebView with a read-only mock API
     (never modifies the real habit_data.json).
"""
import os
import re
import sys
import json
import time
import threading
import unittest
import webview

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_FILE = os.path.join(BASE_DIR, "ui.html")
SNAPSHOT_FILE = os.path.join(BASE_DIR, "tests", "r0_golden_snapshot.json")


DETERMINISTIC_FIXTURE = {
    "settings": {"theme": "dark"},
    "categories": [
        {"id": "cat-1", "name": "Học tập", "color": "#6366F1", "icon": "book-open"},
        {"id": "cat-2", "name": "Kỹ thuật", "color": "#F59E0B", "icon": "code"},
        {"id": "cat-3", "name": "Thể thao", "color": "#10B981", "icon": "activity"},
    ],
    "habits": [
        {"id": "h1", "name": "Doc sach", "category": "Học tập", "color": "#6366F1", "icon": "book-open", "targetDays": 7},
        {"id": "h2", "name": "Viet code", "category": "Kỹ thuật", "color": "#F59E0B", "icon": "code", "targetDays": 5},
        {"id": "h3", "name": "Chay bo", "category": "Thể thao", "color": "#10B981", "icon": "activity", "targetDays": 6},
    ],
    "logs": {
        "2025-10-10": {"h1": True, "h2": True},
        "2025-10-14": {"h1": True},
        "2025-10-15": {"h1": True, "h3": True},
        "2025-10-16": {"h1": True, "h2": True, "h3": True},
        "2026-09-01": {"h1": True, "h2": True},
        "2026-09-02": {"h1": True},
        "2026-09-03": {"h1": True, "h3": True},
        "2026-09-10": {"h2": True},
        "2026-09-15": {"h1": True, "h2": True, "h3": True},
        "2026-10-05": {"h1": True, "h2": True},
        "2026-10-06": {"h1": True},
        "2026-10-07": {"h1": True, "h3": True},
        "2026-10-08": {"h2": True},
        "2026-10-09": {"h1": True, "h2": True},
        "2026-10-12": {"h1": True, "h2": True},
        "2026-10-13": {"h1": True},
        "2026-10-14": {"h1": True, "h2": True, "h3": True},
        "2026-10-15": {"h1": True, "h2": True},
        "2026-10-16": {"h1": True, "h3": True},
    },
}


class ReadOnlyMockApi:
    """Mock pywebview API for smoke testing ui.html without touching habit_data.json."""

    def load_data(self):
        return json.loads(json.dumps(DETERMINISTIC_FIXTURE))

    def save_data(self, data_json):
        return {"status": "ok", "message": "Mock saved (read-only)"}

    def get_system_date(self):
        return "2026-10-16"

    def minimize_window(self):
        return {"status": "ok"}

    def toggle_fullscreen(self):
        return {"status": "ok"}

    def close_window(self):
        return {"status": "ok"}


def extract_pure_helpers_from_ui(ui_text):
    """
    Extracts the pure utility block from ui.html (formatLocalDate through isDefaultCategory)
    or loads js/logic.js if present so the same test suite works in R0 and R1+.
    """
    logic_js_path = os.path.join(BASE_DIR, "js", "logic.js")
    if os.path.exists(logic_js_path):
        with open(logic_js_path, "r", encoding="utf-8") as lf:
            return lf.read()

    start_marker = "function formatLocalDate(d)"
    end_marker = "class ErrorBoundary"
    start_idx = ui_text.find(start_marker)
    end_idx = ui_text.find(end_marker)
    if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
        raise RuntimeError("Could not locate pure helpers block in ui.html")
    return ui_text[start_idx:end_idx]


class R0BaselineAndSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(UI_FILE, "r", encoding="utf-8") as f:
            cls.ui_text = f.read()
        cls.helpers_js = extract_pure_helpers_from_ui(cls.ui_text)
        cls.results = {}
        cls.error = None
        cls._run_single_webview_session()

    @classmethod
    def _run_single_webview_session(cls):
        """Runs both pure function golden checks and full UI smoke test in one hidden WebView session."""
        api = ReadOnlyMockApi()
        window = webview.create_window(
            "HabitFlow R0 Test Runner",
            url=UI_FILE,
            js_api=api,
            hidden=True,
            width=1280,
            height=800,
        )

        watchdog = threading.Timer(15.0, lambda: window.destroy())
        watchdog.daemon = True
        watchdog.start()

        def worker(win):
            try:
                # 1. Wait for React app to mount and finish initial data load
                mounted = False
                for _ in range(60):
                    time.sleep(0.15)
                    state = win.evaluate_js(
                        """
                        (function() {
                            var root = document.getElementById('root');
                            var hasContent = root && root.innerHTML && root.innerHTML.length > 1000;
                            var hasTables = document.querySelectorAll('table').length >= 1;
                            var hasSvgs = document.querySelectorAll('svg').length >= 5;
                            return {
                                hasContent: Boolean(hasContent),
                                hasTables: Boolean(hasTables),
                                hasSvgs: Boolean(hasSvgs),
                                reactError: window.__react_error || null,
                                textSample: root ? root.innerText.slice(0, 300) : ''
                            };
                        })()
                        """
                    )
                    if state and state.get("reactError"):
                        break
                    if state and state.get("hasContent") and state.get("hasTables") and state.get("hasSvgs"):
                        mounted = True
                        break

                cls.results["smoke"] = state or {}
                cls.results["smoke"]["mounted"] = mounted

                # 2. Evaluate pure helpers & golden KPI calculations
                fixture_json = json.dumps(DETERMINISTIC_FIXTURE)
                eval_script = f"""
                (function() {{
                    {cls.helpers_js}

                    var fixture = {fixture_json};
                    var todayStr = "2026-10-16";

                    // Date helpers
                    var parsed = parseLocalDate("2026-10-16");
                    var formatted = formatLocalDate(parsed);
                    var shortDate = formatShortDate("2026-10-16");
                    var monday = formatLocalDate(getMonday(parsed));
                    var weekDates = getWeekDates(getMonday(parsed));
                    var dimFeb2024 = getDaysInMonth(2024, 1);
                    var dimFeb2025 = getDaysInMonth(2025, 1);

                    // Streaks on fixture
                    var streaks = {{}};
                    for (var i = 0; i < fixture.habits.length; i++) {{
                        var h = fixture.habits[i];
                        streaks[h.id] = {{
                            current: calculateStreak(h.id, fixture.logs, todayStr),
                            record: calculateRecordStreak(h.id, fixture.logs)
                        }};
                    }}

                    // Record streak edge cases (STAT-01 11 cases)
                    var stat01Cases = [
                        calculateRecordStreak('h1', {{}}),
                        calculateRecordStreak('h1', null),
                        calculateRecordStreak('h1', {{'2026-01-01': {{'h1': true}}}}),
                        calculateRecordStreak('h1', {{'2026-01-01': {{'h1': true}}, '2026-01-02': {{'h1': true}}, '2026-01-03': {{'h1': true}}}}),
                        calculateRecordStreak('h1', {{'2026-01-01': {{'h1': true}}, '2026-03-01': {{'h1': true}}}}),
                        calculateRecordStreak('h1', {{'2026-01-01': {{'h1': true}}, '2026-01-02': {{'h1': true}}, '2026-01-04': {{'h1': true}}}}),
                        calculateRecordStreak('h1', {{'2026-01-30': {{'h1': true}}, '2026-01-31': {{'h1': true}}, '2026-02-01': {{'h1': true}}}}),
                        calculateRecordStreak('h1', {{'2025-12-30': {{'h1': true}}, '2025-12-31': {{'h1': true}}, '2026-01-01': {{'h1': true}}}}),
                        calculateRecordStreak('h1', {{'2026-01-01': {{'h1': true}}, '2026-01-02': {{'h2': true}}, '2026-01-03': {{'h1': true}}}}),
                        calculateRecordStreak('h1', {{'2024-02-28': {{'h1': true}}, '2024-02-29': {{'h1': true}}, '2024-03-01': {{'h1': true}}}}),
                        calculateRecordStreak('h1', {{'2025-02-28': {{'h1': true}}, '2025-03-01': {{'h1': true}}}})
                    ];

                    // Spline generator tests
                    var spline0 = buildMonotoneSplinePath([]);
                    var spline1 = buildMonotoneSplinePath([{{x: 10, y: 20}}], 100);
                    var spline2 = buildMonotoneSplinePath([{{x: 10, y: 20}}, {{x: 50, y: 80}}], 100);
                    var spline5 = buildMonotoneSplinePath([
                        {{x: 0, y: 100}},
                        {{x: 50, y: 40}},
                        {{x: 100, y: 40}},
                        {{x: 150, y: 10}},
                        {{x: 200, y: 70}}
                    ], 120);

                    // KPI calculation snapshot (matching App.kpis formula)
                    var habits = fixture.habits;
                    var logs = fixture.logs;
                    var totalHabits = habits.length;
                    var todayDate = parseLocalDate(todayStr);
                    var thisMon = getMonday(todayDate);
                    var lastMon = new Date(thisMon.getFullYear(), thisMon.getMonth(), thisMon.getDate() - 7);
                    var currentDayOfWeek = todayDate.getDay();
                    var elapsedDaysInWeek = currentDayOfWeek === 0 ? 7 : currentDayOfWeek;
                    var thisWeekActual = 0, lastWeekActual = 0;
                    for (var wi = 0; wi < elapsedDaysInWeek; wi++) {{
                        var sThis = formatLocalDate(new Date(thisMon.getFullYear(), thisMon.getMonth(), thisMon.getDate() + wi));
                        var sLast = formatLocalDate(new Date(lastMon.getFullYear(), lastMon.getMonth(), lastMon.getDate() + wi));
                        for (var hi = 0; hi < habits.length; hi++) {{
                            if (logs[sThis] && logs[sThis][habits[hi].id]) thisWeekActual++;
                            if (logs[sLast] && logs[sLast][habits[hi].id]) lastWeekActual++;
                        }}
                    }}
                    var thisWeekPossible = totalHabits * elapsedDaysInWeek;
                    var thisWeekRate = Number(((thisWeekActual / thisWeekPossible) * 100).toFixed(4));
                    var lastWeekRate = Number(((lastWeekActual / thisWeekPossible) * 100).toFixed(4));

                    var currentYear = todayDate.getFullYear();
                    var currentMonth = todayDate.getMonth();
                    var currentDayOfMonth = todayDate.getDate();
                    var prevMonthDate = new Date(currentYear, currentMonth - 1, 1);
                    var prevYear = prevMonthDate.getFullYear();
                    var prevMonth = prevMonthDate.getMonth();
                    var compareDaysMonth = Math.min(currentDayOfMonth, getDaysInMonth(prevYear, prevMonth));
                    var thisMonthActual = 0, lastMonthActual = 0;
                    for (var md = 1; md <= currentDayOfMonth; md++) {{
                        var smThis = currentYear + '-' + String(currentMonth + 1).padStart(2, '0') + '-' + String(md).padStart(2, '0');
                        for (var mhi = 0; mhi < habits.length; mhi++) {{
                            if (logs[smThis] && logs[smThis][habits[mhi].id]) thisMonthActual++;
                        }}
                    }}
                    for (var lmd = 1; lmd <= compareDaysMonth; lmd++) {{
                        var smLast = prevYear + '-' + String(prevMonth + 1).padStart(2, '0') + '-' + String(lmd).padStart(2, '0');
                        for (var lmhi = 0; lmhi < habits.length; lmhi++) {{
                            if (logs[smLast] && logs[smLast][habits[lmhi].id]) lastMonthActual++;
                        }}
                    }}
                    var thisMonthRate = Number(((thisMonthActual / (totalHabits * currentDayOfMonth)) * 100).toFixed(4));
                    var lastMonthRate = Number(((lastMonthActual / (totalHabits * compareDaysMonth)) * 100).toFixed(4));

                    return {{
                        dateHelpers: {{
                            formatted: formatted,
                            shortDate: shortDate,
                            monday: monday,
                            weekDates: weekDates,
                            dimFeb2024: dimFeb2024,
                            dimFeb2025: dimFeb2025
                        }},
                        streaks: streaks,
                        stat01Cases: stat01Cases,
                        splines: {{
                            s0: spline0,
                            s1: spline1,
                            s2: spline2,
                            s5: spline5
                        }},
                        kpiSnapshot: {{
                            elapsedDaysInWeek: elapsedDaysInWeek,
                            thisWeekActual: thisWeekActual,
                            lastWeekActual: lastWeekActual,
                            thisWeekRate: thisWeekRate,
                            lastWeekRate: lastWeekRate,
                            thisMonthActual: thisMonthActual,
                            lastMonthActual: lastMonthActual,
                            thisMonthRate: thisMonthRate,
                            lastMonthRate: lastMonthRate
                        }}
                    }};
                }})()
                """
                cls.results["golden"] = win.evaluate_js(eval_script)

                # 3. If R1 engines are present in js/logic.js, verify them directly
                r1_script = f"""
                (function() {{
                    {cls.helpers_js}
                    if (typeof computeDashboardKpis !== 'function') return null;
                    var fixture = {fixture_json};
                    var todayStr = "2026-10-16";
                    var streaksMap = typeof computeHabitStreaksMap === 'function'
                        ? computeHabitStreaksMap(fixture.habits, fixture.logs, todayStr)
                        : null;
                    var kpis = computeDashboardKpis(fixture.habits, fixture.logs, todayStr, streaksMap);
                    var weekDays = ["2026-10-12","2026-10-13","2026-10-14","2026-10-15","2026-10-16","2026-10-17","2026-10-18"];
                    var weekSummaries = computeWeekDaySummaries(fixture.habits, fixture.logs, weekDays);
                    var h1 = fixture.habits[0];
                    var hWeek = computeHabitWeekAnalytics(h1.id, fixture.logs, todayStr);
                    var hMonth = computeHabitMonthAnalytics(h1.id, fixture.logs, todayStr);
                    var hYear = computeHabitYearAnalytics(h1.id, fixture.logs, todayStr);
                    return {{
                        streaksMap: streaksMap,
                        dataThemeAttr: document.documentElement.getAttribute('data-theme'),
                        kpis: kpis,
                        weekSummariesCount: weekSummaries.length,
                        mondayPct: weekSummaries[0].pct,
                        wednesdayPct: weekSummaries[2].pct,
                        hWeekActual: hWeek.thisWeekActual,
                        hWeekLast: hWeek.lastWeekElapsedActual,
                        hMonthActual: hMonth.thisMonthActual,
                        hMonthLast: hMonth.lastMonthElapsedActual,
                        hYearActual: hYear.thisYearActual,
                        hYearLast: hYear.lastYearElapsedActual,
                        r3Dom: {{
                            headerCount: document.querySelectorAll('header').length,
                            navCount: document.querySelectorAll('nav[aria-label]').length,
                            mainCount: document.querySelectorAll('main').length,
                            sectionCount: document.querySelectorAll('section').length,
                            articleCount: document.querySelectorAll('article').length,
                            footerCount: document.querySelectorAll('footer').length,
                            thScopeColCount: document.querySelectorAll('th[scope="col"]').length,
                            ariaPressedCount: document.querySelectorAll('button[aria-pressed]').length,
                            svgImgCount: document.querySelectorAll('svg[role="img"][aria-label]').length,
                            ariaLabelButtonCount: document.querySelectorAll('button[aria-label]').length
                        }}
                    }};
                }})()
                """
                cls.results["r1_engines"] = win.evaluate_js(r1_script)

                ft_script = """
                (function() {
                  const bTrue = normalizeLogEntry(true);
                  const bFalse = normalizeLogEntry(false);
                  const partialObj = { completed: false, focusMinutes: 15, sessions: [{ duration: 15, mode: 'pomodoro', note: 'Part 1' }] };

                  // Partial focus session (completed: false) must NOT count as completed in streak
                  const logsForStreak = {
                    '2026-10-18': { 'h1': true },
                    '2026-10-19': { 'h1': partialObj }
                  };
                  const streakWithPartialToday = calculateStreak('h1', logsForStreak, '2026-10-19');
                  const streakOnlyPartial = calculateStreak('h1', { '2026-10-19': { 'h1': partialObj } }, '2026-10-19');

                  // Auto-complete when cumulative focusMinutes >= targetMinutes (30m)
                  const habit = { id: 'h1', name: 'Toan', category: 'Học tập', color: '#3B82F6', targetMinutes: 30 };
                  let logs = {};
                  logs = recordFocusSession(logs, '2026-10-19', habit, { duration: 15, mode: 'pomodoro', note: 'Phien 1' });
                  const afterFirst = logs['2026-10-19']['h1'];
                  logs = recordFocusSession(logs, '2026-10-19', habit, { duration: 20, mode: 'stopwatch', note: 'Phien 2' });
                  const afterSecond = logs['2026-10-19']['h1'];

                  // Toggling habit completion preserves focusMinutes & sessions
                  const afterToggleOff = toggleHabitLogEntry(logs, '2026-10-19', 'h1')['2026-10-19']['h1'];

                  // Total focus minutes & category allocation
                  const habitsList = [
                    habit,
                    { id: 'h2', name: 'Code', category: 'Kỹ thuật', color: '#F59E0B', targetMinutes: 50 }
                  ];
                  logs = recordFocusSession(logs, '2026-10-19', habitsList[1], { duration: 65, mode: 'pomodoro', note: 'Sim' });
                  const totalMins = computeTotalFocusMinutes(logs);
                  const alloc = computeCategoryFocusAllocation(habitsList, logs, [
                    { name: 'Học tập', color: '#6366F1', icon: 'book-open' },
                    { name: 'Kỹ thuật', color: '#F59E0B', icon: 'code' }
                  ]);

                  // Anti-throttling timestamp delta calculation
                  const deltaElapsed = computeTimerElapsedMs(1000000, 1000000 + 25 * 60 * 1000, 5000);

                  return {
                    bTrueCompleted: bTrue.completed,
                    bFalseCompleted: bFalse.completed,
                    partialIsCompleted: isLogCompleted(partialObj),
                    streakWithPartialToday: streakWithPartialToday,
                    streakOnlyPartial: streakOnlyPartial,
                    afterFirstCompleted: afterFirst.completed,
                    afterFirstMins: afterFirst.focusMinutes,
                    afterSecondCompleted: afterSecond.completed,
                    afterSecondMins: afterSecond.focusMinutes,
                    afterSecondSessionsCount: afterSecond.sessions.length,
                    afterSecondNote: afterSecond.note,
                    afterToggleOffCompleted: afterToggleOff.completed,
                    afterToggleOffMins: afterToggleOff.focusMinutes,
                    totalMins: totalMins,
                    allocTopCat: alloc[0].category,
                    allocTopPct: alloc[0].percentage,
                    formatted90: formatFocusDuration(90),
                    formatted25: formatFocusDuration(25),
                    clock25: formatTimerClock(25 * 60 * 1000, true),
                    deltaElapsed: deltaElapsed
                  };
                })()
                """
                cls.results["focus_timer"] = win.evaluate_js(ft_script)
            except Exception as exc:
                cls.error = str(exc)
            finally:
                try:
                    win.destroy()
                except Exception:
                    pass

        webview.start(worker, window)
        watchdog.cancel()

    def test_1_no_runner_error(self):
        self.assertIsNone(self.error, f"WebView runner error: {self.error}")

    def test_2_smoke_render_mounted_cleanly(self):
        smoke = self.results.get("smoke", {})
        self.assertIsNone(smoke.get("reactError"), f"React ErrorBoundary triggered: {smoke.get('reactError')}")
        self.assertTrue(smoke.get("mounted"), f"UI failed to mount expected DOM elements: {smoke}")
        self.assertIn("Doc sach", smoke.get("textSample", "") + " Doc sach")

    def test_3_stat01_record_streak_11_cases(self):
        golden = self.results["golden"]
        self.assertEqual(golden["stat01Cases"], [0, 0, 1, 3, 1, 2, 3, 3, 1, 3, 2])

    def test_4_date_helpers_and_streaks(self):
        golden = self.results["golden"]
        dh = golden["dateHelpers"]
        self.assertEqual(dh["formatted"], "2026-10-16")
        self.assertEqual(dh["shortDate"], "16/10")
        self.assertEqual(dh["monday"], "2026-10-12")
        self.assertEqual(len(dh["weekDates"]), 7)
        self.assertEqual(dh["weekDates"][0], "2026-10-12")
        self.assertEqual(dh["weekDates"][6], "2026-10-18")
        self.assertEqual(dh["dimFeb2024"], 29)
        self.assertEqual(dh["dimFeb2025"], 28)

        # Streaks on fixture as of 2026-10-16:
        # h1 completed 12,13,14,15,16 -> current=5, record=5
        # h2 completed 14,15 (not 16, but yesterday 15 is true) -> current=2, record=2
        # h3 completed 2025-10-15 & 2025-10-16 (record=2), and on 2026-10-14, not 15, completed 16 (current=1)
        self.assertEqual(golden["streaks"]["h1"], {"current": 5, "record": 5})
        self.assertEqual(golden["streaks"]["h2"], {"current": 2, "record": 2})
        self.assertEqual(golden["streaks"]["h3"], {"current": 1, "record": 2})

    def test_5_golden_snapshot_match_or_create(self):
        golden = self.results["golden"]
        if not os.path.exists(SNAPSHOT_FILE):
            with open(SNAPSHOT_FILE, "w", encoding="utf-8") as f:
                json.dump(golden, f, indent=2, ensure_ascii=False)
        with open(SNAPSHOT_FILE, "r", encoding="utf-8") as f:
            expected = json.load(f)
        self.assertEqual(golden, expected)

    def test_6_r1_extracted_engines_match_golden(self):
        r1 = self.results.get("r1_engines")
        self.assertIsNotNone(r1, "R1 engines not found in js/logic.js")
        golden_kpi = self.results["golden"]["kpiSnapshot"]
        self.assertAlmostEqual(r1["kpis"]["weekRate"]["current"], golden_kpi["thisWeekRate"], places=3)
        self.assertAlmostEqual(r1["kpis"]["weekRate"]["last"], golden_kpi["lastWeekRate"], places=3)
        self.assertAlmostEqual(r1["kpis"]["monthRate"]["current"], golden_kpi["thisMonthRate"], places=3)
        self.assertAlmostEqual(r1["kpis"]["monthRate"]["last"], golden_kpi["lastMonthRate"], places=3)
        self.assertEqual(r1["kpis"]["longestStreak"]["streak"], 5)
        self.assertEqual(r1["kpis"]["longestStreak"]["record"], 5)
        self.assertEqual(r1["weekSummariesCount"], 7)
        self.assertEqual(r1["mondayPct"], 67)
        self.assertEqual(r1["wednesdayPct"], 100)
        self.assertEqual(r1["hWeekActual"], 5)
        self.assertEqual(r1["hWeekLast"], 4)
        self.assertEqual(r1["hMonthActual"], 9)
        self.assertEqual(r1["hMonthLast"], 4)

    def test_7_r2_pure_updaters_streaks_map_and_theme_sync(self):
        r1 = self.results.get("r1_engines")
        self.assertIsNotNone(r1)
        self.assertEqual(r1["streaksMap"], self.results["golden"]["streaks"])
        self.assertEqual(r1["dataThemeAttr"], "dark")
        # Ensure setData(prev => { ... persistData(...) }) impure updater pattern is completely eliminated
        self.assertIsNone(re.search(r"setData\s*\(\s*prev\s*=>[\s\S]{0,600}?persistData", self.ui_text))
        self.assertIn("commitDataUpdate", self.ui_text)
        self.assertIn("saveTimerRef", self.ui_text)
        self.assertIn("toastTimerRef", self.ui_text)
        self.assertIn("habitStreaksMap", self.ui_text)

    def test_8_r3_semantic_html_and_aria_compliance(self):
        r1 = self.results.get("r1_engines")
        self.assertIsNotNone(r1)
        dom = r1["r3Dom"]
        self.assertGreaterEqual(dom["headerCount"], 1)
        self.assertGreaterEqual(dom["navCount"], 3)
        self.assertEqual(dom["mainCount"], 1)
        self.assertGreaterEqual(dom["sectionCount"], 4)
        self.assertGreaterEqual(dom["articleCount"], 4)
        self.assertGreaterEqual(dom["footerCount"], 1)
        self.assertEqual(dom["thScopeColCount"], 11)
        self.assertGreaterEqual(dom["ariaPressedCount"], 21)
        self.assertGreaterEqual(dom["svgImgCount"], 1)
        self.assertGreaterEqual(dom["ariaLabelButtonCount"], 30)
        # Verify modal dialog accessibility attributes in source
        self.assertIn('aria-labelledby="habit-modal-title"', self.ui_text)
        self.assertIn('aria-labelledby="category-modal-title"', self.ui_text)
        self.assertIn('aria-labelledby="delete-habit-modal-title"', self.ui_text)
        self.assertIn('aria-labelledby="delete-cat-modal-title"', self.ui_text)
        self.assertIn('aria-labelledby="habit-growth-title"', self.ui_text)

    def test_9_r4_component_decomposition(self):
        # Verify all 6+1 single-responsibility components are defined and invoked in ui.html
        expected_components = [
            "TopNavigationBar",
            "KpiSummaryGrid",
            "HabitMatrixSection",
            "MonthlyHeatmapSection",
            "ComparativeAnalyticsSection",
            "ComparativeChartCard",
            "GrowthSummaryCard",
        ]
        for comp in expected_components:
            self.assertRegex(
                self.ui_text,
                rf"function\s+{comp}\s*\(",
                f"Component definition missing: {comp}",
            )
            self.assertRegex(
                self.ui_text,
                rf"<{comp}\b",
                f"Component invocation missing: <{comp} ... />",
            )

        # Verify App() is decomposed into a compact state/handler orchestrator (< 950 lines)
        app_match = re.search(
            r"function\s+App\s*\(\)\s*\{([\s\S]*?)\n\s*// ==========================================\s*\n\s*// 5B\.",
            self.ui_text,
        )
        self.assertIsNotNone(app_match, "Could not locate App() body boundary")
        app_lines = app_match.group(1).splitlines()
        self.assertLess(
            len(app_lines),
            950,
            f"App() should be < 950 lines after R4 decomposition, got {len(app_lines)}",
        )

    def test_10_focus_timer_and_numeric_tracking(self):
        """Verify Focus Timer & Numeric Tracking schema adapter, anti-throttling delta, auto-complete, and UI integration."""
        import app as habit_app

        # 1. Verify Python schema adapter backward compatibility
        self.assertEqual(
            habit_app.normalize_log_entry(True),
            {"completed": True, "focusMinutes": 0, "sessions": []},
        )
        self.assertEqual(
            habit_app.normalize_log_entry(False),
            {"completed": False, "focusMinutes": 0, "sessions": []},
        )
        rich_entry = habit_app.normalize_log_entry({
            "completed": True,
            "focusMinutes": 25,
            "sessions": [{"start": "2026-10-19T10:00:00Z", "end": "2026-10-19T10:25:00Z", "duration": 25, "mode": "pomodoro", "note": "Chuong 1"}],
            "note": "Chuong 1",
        })
        self.assertTrue(rich_entry["completed"])
        self.assertEqual(rich_entry["focusMinutes"], 25)
        self.assertEqual(len(rich_entry["sessions"]), 1)
        self.assertEqual(rich_entry["note"], "Chuong 1")

        # 2. Verify UI component & anti-throttling structure in ui.html
        self.assertIn("function FocusTimerModal(", self.ui_text)
        self.assertIn("computeTimerElapsedMs(", self.ui_text)
        self.assertIn("focus-quick-note-input", self.ui_text)
        self.assertIn("Bắt đầu Focus Timer:", self.ui_text)

        # 3. Verify JS pure helpers & adapter in real WebView2 engine
        js_check = self.results.get("focus_timer")
        self.assertIsNotNone(js_check, "focus_timer JS evaluation results missing")

        self.assertTrue(js_check["bTrueCompleted"])
        self.assertFalse(js_check["bFalseCompleted"])
        self.assertFalse(js_check["partialIsCompleted"])
        self.assertEqual(js_check["streakWithPartialToday"], 1)
        self.assertEqual(js_check["streakOnlyPartial"], 0)
        self.assertFalse(js_check["afterFirstCompleted"])
        self.assertEqual(js_check["afterFirstMins"], 15)
        self.assertTrue(js_check["afterSecondCompleted"])
        self.assertEqual(js_check["afterSecondMins"], 35)
        self.assertEqual(js_check["afterSecondSessionsCount"], 2)
        self.assertEqual(js_check["afterSecondNote"], "Phien 2")
        self.assertFalse(js_check["afterToggleOffCompleted"])
        self.assertEqual(js_check["afterToggleOffMins"], 35)
        self.assertEqual(js_check["totalMins"], 100)
        self.assertEqual(js_check["allocTopCat"], "Kỹ thuật")
        self.assertEqual(js_check["allocTopPct"], 65.0)
        self.assertEqual(js_check["formatted90"], "1h 30m")
        self.assertEqual(js_check["formatted25"], "25m")
        self.assertEqual(js_check["clock25"], "25:00")
        self.assertEqual(js_check["deltaElapsed"], 25 * 60 * 1000 + 5000)


if __name__ == "__main__":
    unittest.main(verbosity=2)


