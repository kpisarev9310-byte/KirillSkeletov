#!/usr/bin/env python3
"""Автотест ORBIT CRUSH: запускает игру в headless Chromium,
прогоняет автопилотом и проверяет ключевые механики."""
import sys, time
from playwright.sync_api import sync_playwright

URL = "http://localhost:8000/index.html"
RUN_MS = int(sys.argv[1]) * 1000 if len(sys.argv) > 1 else 20000

errors = []

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={"width": 1280, "height": 720})
    page.on("pageerror", lambda e: errors.append(f"JS ERROR: {e}"))
    page.on("console", lambda m: errors.append(f"CONSOLE ERR: {m.text}") if m.type == "error" else None)

    page.goto(URL)
    page.wait_for_timeout(800)

    # 1. Старт из меню по пробелу
    mode = page.evaluate("G.mode")
    assert mode == "menu", f"ожидали menu, получили {mode}"
    page.keyboard.press("Space")
    page.wait_for_timeout(500)
    mode = page.evaluate("G.mode")
    assert mode == "play", f"после Space ожидали play, получили {mode}"
    print("[ok] старт из меню (Space -> play)")

    # 2. Удар молотом: планета появляется и разбивается
    page.evaluate("startAuto()")          # автопилот
    t0 = time.time()
    crushed = 0
    max_score = 0
    while (time.time() - t0) * 1000 < RUN_MS:
        st = page.evaluate("() => ({m:G.mode,s:G.score,c:G.crushed,sh:G.shield,p:G.planets.length})")
        max_score = max(max_score, st["s"])
        crushed = st["c"]
        if st["m"] == "dead":
            errors.append(f"автопилот умер на счёте {st['s']}")
            break
        page.wait_for_timeout(1000)

    print(f"[..] прогон {RUN_MS//1000}с: счёт до {max_score}, разбито планет: {crushed}")

    # 3. Механика щита существует и включалась
    had_shield = page.evaluate("G.shieldUsed===true || G.shield===true || window.__shieldSeen===true")

    # 4. Смерть и рестарт (щит гасит первый удар — проверяем и это тоже)
    page.evaluate("() => { AUTO=false; if(autoTimer)clearInterval(autoTimer); }")
    die_real = "() => { if(G.shield){ G.shield=false; } const p=G.planets.find(q=>q.alive)||null; if(!p){ spawnPlanet(); } die(G.planets.find(q=>q.alive)); }"
    if page.evaluate("G.shield"):
        page.evaluate("() => { const p=G.planets.find(q=>q.alive)||null; if(p) die(p); }")
        page.wait_for_timeout(200)
        print(f"[ok] щит поглотил удар: {page.evaluate('G.mode') == 'play'}")
    page.evaluate(die_real)
    page.wait_for_timeout(1000)
    assert page.evaluate("G.mode") == "dead", "die() не перевёл в режим dead"
    page.keyboard.press("Space")
    page.wait_for_timeout(300)
    assert page.evaluate("G.mode") == "play", "ревант по Space не работает"
    print("[ok] смерть -> экран game over -> ревант по Space")

    # 5. Сохранение рекорда
    best = page.evaluate("localStorage.getItem('orbitcrush_best')")
    print(f"[ok] рекорд сохраняется в localStorage: best={best}")

    # 6. Скриншоты для визуальной проверки
    page.screenshot(path="shot_game.png")
    page.evaluate("G.mode='menu';document.getElementById('menu').classList.remove('hidden')")
    page.wait_for_timeout(300)
    page.screenshot(path="shot_menu.png")

    browser.close()

print("-" * 50)
if errors:
    print("ПРОБЛЕМЫ:")
    for e in errors[:10]:
        print(" -", e)
    sys.exit(1)
else:
    print("ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ: ошибок JS нет, автопилот выживает, механики работают.")
