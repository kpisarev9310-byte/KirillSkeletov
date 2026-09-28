#!/usr/bin/env python3
"""Автотест ORBIT CRUSH v2: headless Chromium + автопилот.
Проверяет: старт, выживание робота (с бомбами/призраками/кристаллами),
жизни и проигрыш, смерть от бомбы при спаме, ревант, рекорд."""
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
    assert page.evaluate("G.lives") == 3, "на старте должно быть 3 жизни"
    print("[ok] старт из меню, 3 жизни на HUD")

    # 2. Автопилот: робот бьёт всё кроме бомб -> обязан выживать
    page.evaluate("startAuto()")
    t0, max_score, crushed, seen_types = time.time(), 0, 0, set()
    while (time.time() - t0) * 1000 < RUN_MS:
        st = page.evaluate("""() => ({m:G.mode,s:G.score,c:G.crushed,l:G.lives,
            types:[...new Set(G.planets.map(p=>p.type))], ghostVis:G.planets.some(p=>p.type==='ghost'&&p.visible)})""")
        max_score = max(max_score, st["s"]); crushed = st["c"]
        seen_types.update(st["types"])
        if st["m"] == "dead":
            errors.append(f"автопилот умер на счёте {st['s']} (жизней было {st['l']})")
            break
        if st["l"] < 3:
            errors.append(f"автопилот потерял жизнь на счёте {st['s']} — нечестный удар?")
        page.wait_for_timeout(1000)
    print(f"[..] прогон {RUN_MS//1000}с: счёт до {max_score}, разбито {crushed}, типы в игре: {sorted(seen_types)}")
    for need in ("bomb", "ice", "core"):
        if need not in seen_types and max_score > 700:
            errors.append(f"тип {need} так и не появился при счёте {max_score}")

    # 3. Спам-игрок обязан ПРОИГРАТЬ: бьёт вслепую -> детонирует бомбы
    page.evaluate("() => { AUTO=false; if(autoTimer)clearInterval(autoTimer); }")
    page.evaluate("startGame(); G.score=800;")   # чтобы бомбы точно спавнились
    spam_dead = False
    t0 = time.time()
    while (time.time() - t0) < 40 and not spam_dead:
        page.keyboard.press("Space")             # спам без ритма
        page.wait_for_timeout(90)
        st = page.evaluate("() => ({m:G.mode,l:G.lives})")
        if st["m"] == "dead":
            spam_dead = True
    cause = page.evaluate("document.getElementById('cause').textContent")
    assert spam_dead, "спам-игрок выжил 40 секунд — игра слишком лёгкая!"
    print(f"[ok] проигрыш реален: спам умер, причина на экране: «{cause}»")

    # 4. Ревант и сброс жизней
    page.wait_for_timeout(900)
    page.keyboard.press("Space")
    page.wait_for_timeout(300)
    assert page.evaluate("G.mode") == "play" and page.evaluate("G.lives") == 3, "ревант не сбросил жизни"
    print("[ok] ревант: снова play, 3 жизни")

    # 5. Прямая проверка: потеря 3 жизней = game over
    page.evaluate("() => { G.shield=false; loseLife(CX,CY,'ТЕСТ'); loseLife(CX,CY,'ТЕСТ'); loseLife(CX,CY,'ТЕСТ'); }")
    page.wait_for_timeout(300)
    assert page.evaluate("G.mode") == "dead", "три потери жизни не привели к смерти"
    print("[ok] 3 потери жизни -> game over")

    # 6. Рекорд
    best = page.evaluate("localStorage.getItem('orbitcrush_best')")
    print(f"[ok] рекорд в localStorage: best={best}")

    # 7. Скриншоты
    page.evaluate("() => { startGame(); G.score=1500; updateHUD(); }")
    page.wait_for_timeout(2500)
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
    print("ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ: ошибок JS нет, автопилот выживает, спам проигрывает, механики работают.")
