"""Исполняемое описание текущего скоринга (базовая линия на 06.09.2026).

У каждого параметра в RULE_SPECS есть русское описание и стандартная ставка.
Отметки сломов ведущим проверяются по последнему сохранённому scoring_marks:
ни одна отметка не заменяет проверку фактических голосов, ролей и уходов.
Положительный/отрицательный тест проверяет все десять результатов и записи
breakdown, в том числе при изменённой админской ставке и подписи. Ожидания
сценариев заданы отдельно от проверяемого расчёта.

Это unit-тесты потребителя игровых событий, а не Redis/API или полного хода
партии. Минимальные журналы намеренно изолируют правила. Текущие особенности
описаны явно: тесты фиксируют поведение, а не исправляют замечания ревью.
Исходные примеры ветвей адаптированы из отчёта scoring-review-2026-09-06;
этот файл автономен, не импортирует отчёт и не запускает его скрипты.

Запуск из backend: python -B -m unittest discover -s tests -v
"""
import copy
import unittest
from decimal import Decimal

from app.services.game_scoring import (
    GAME_SCORING_RULE_DEFAULTS,
    build_game_scoring_rules_snapshot,
    calculate_game_points,
    calculate_game_points_breakdown,
    calculate_game_scoring_audit,
    normalize_game_points_value,
    parse_game_scoring_marks,
)

IDS = list(range(1, 11))
ROLES = {str(i): "citizen" for i in IDS}
ROLES.update({"1": "sheriff", "8": "mafia", "9": "mafia", "10": "don"})
BOUNDS = {"additional_points_min", "additional_points_max"}

# Ключ: (стандартный балл, правило применения).
RULE_SPECS = {
    "vote_break_red_to_red": (-0.5, "Один раз отмеченному ведущим красному: в день 1 он голосовал за единственного ушедшего красного без подъёма; сам ушёл либо единственным лидером без подъёма в день 2, либо по фолам, техфолам или самоубийством в день 1/2. Для удаления в день 1 наступление дня 2 не требуется. Обычные штрафы удаления складываются со штрафом слома. Последний сохранённый выбор определяет получателя."),
    "vote_break_red_to_black": (0.2, "Один раз отмеченному красному: в день 1 голосовал за единственного ушедшего чёрного без подъёма, день 2 наступил и в этот день сам не ушёл через голосование, в том числе подъём. Уход по фолам, техфолам или самоубийством в день 1/2 отменяет бонус; ночной отстрел и такие удаления начиная с дня 3 его не отменяют."),
    "vote_break_black_to_sheriff": (0.2, "Один раз отмеченному чёрному: в день 1 голосовал за фактически ушедшего шерифа, единственного лидера без подъёма. Второй день и победа команды не требуются. Снятая ведущим отметка исключает начисление."),
    "additional_points_min": (-1, "Нижняя граница применяется один раз к сумме всех допбаллов, до прибавления базы. Настраивается; положительная граница поднимает даже нулевую сумму."),
    "additional_points_max": (1, "Верхняя граница применяется один раз к сумме всех допбаллов, до прибавления базы. Настраивается и может превышать +1."),
    "fourth_foul": (-0.3, "Четвёртый фол со связанным уходом по фолам без признака поражения/ППК. Первые три фола не штрафуются."),
    "fourth_foul_lost": (-0.5, "Четвёртый фол со связанным уходом, где game_lost_after или ППК истинны; заменяет обычный штраф."),
    "tech_foul": (-0.15, "Первый техфол и второй без поражения дают отдельный штраф каждый; событие ухода для обычной ставки не требуется."),
    "second_tech_foul_lost": (-0.35, "Второй техфол при уходе по фолам с поражением/ППК заменяет обычную ставку второго техфола. Первый штраф сохраняется."),
    "suicide": (-0.3, "Каждый уход с причиной suicide без game_lost_after даёт обычный штраф независимо от финального победителя."),
    "suicide_lost": (-0.5, "Самоубийство с game_lost_after даёт повышенный штраф вместо обычного независимо от финального победителя."),
    "best_move_black_0": (-0.1, "Красному автору события лучшего хода за ноль уникальных чёрных целей, включая пустой список. Без самого события скорер ничего не начисляет."),
    "best_move_black_1": (0, "Красному автору лучшего хода за одну уникальную чёрную цель. Стандартная ставка нулевая, но правило срабатывает и настраивается."),
    "best_move_black_2": (0.2, "Красному автору лучшего хода за две уникальные чёрные цели независимо от числа красных целей."),
    "best_move_black_3": (0.4, "Красному автору лучшего хода за три уникальные чёрные цели. Повтор одной цели не увеличивает количество."),
    "night_shoot_miss": (-0.2, "При неуспешном отстреле без упущенной гарантированной победы штрафуется только третий из трёх чёрных, если двое выбрали одну цель, а он другую или не стрелял. Двое, одиночка и три разных цели не штрафуются."),
    "night_shoot_miss_terminal": (-0.5, "При black_wins_if_kill и неуспешном отстреле штрафуется выделенный третий из троих либо единственный чёрный. Двое и трое без большинства не штрафуются. Заменяет обычный промах."),
    "night_self_shot_black_win_1": (0.25, "Чёрному, указанному жертвой успешного отстрела первой ночи, при итоговой победе чёрных. Красная жертва и другой итог не подходят."),
    "night_self_shot_black_win_2": (0.15, "Чёрному, указанному жертвой успешного отстрела второй ночи, при итоговой победе чёрных. Другие ночи не подходят."),
    "vote_opponent_team": (0.15, "Начиная со второго дня голосовавшему против команды за единственного лидера с will_eliminate. Подъём исключён. Текущий скорер использует событие vote, не требует отдельного death и не объединяет повторные события."),
    "vote_red_day_one_compensation": (0.15, "Красному, ушедшему в первый день с причиной vote и vote_unique, без vote_lift. Другие дни и массовый подъём не подходят."),
    "vote_red_terminal": (-0.2, "Красному из by, голосовавшему за красного при единственном vote-уходе с result_after=black, кроме 3в3. Массовый подъём исключён."),
    "vote_red_terminal_3v3": (-0.3, "Красному из by, голосовавшему за красного при единственном vote-уходе с result_after=black и составом 3в3. Заменяет обычный штраф голосования на поражение."),
    "black_win_3v3": (0.3, "Один раз каждому чёрному при итоговой победе чёрных и конечном составе 3в3, независимо от причины ухода. Состав восстанавливается по всем уходам журнала; промежуточный состав подъёма не считается итогом."),
    "black_win_2v2_1v1_alive": (0.2, "Один раз каждому живому чёрному при итоговой победе чёрных на 2в2/1в1 независимо от причины ухода. Учитываются все уходы до завершения партии."),
    "black_win_2v2_1v1_dead": (0.1, "При итоговой победе чёрных на 2в2/1в1 каждому мёртвому чёрному вместо бонуса живому. При другом итоговом результате бонуса нет."),
    "vote_lift_same_team": (-0.3, "Участнику by успешного подъёма минимум двух уникальных целей, если все цели его команды, включая его самого. Смешанный состав не оценивается; скорер опирается на vote."),
    "vote_lift_opponent_team": (0.3, "Участнику by успешного подъёма минимум двух уникальных целей, если все они противоположной команды. Смешанный состав и непринятый подъём не оцениваются."),
    "nomination_black_prevents_black_win": (-0.5, "Чёрному номинатору единственного чёрного кандидата первого сохранённого vote дня, реально ушедшего через vote. Более четырёх живых, критичность B>=R-2 при B>0, после номинации нет запланированной красной речи, в vote-уходах дня нет победы чёрных. Очевидность не нужна."),
    "nomination_red_last_hope": (0.3, "Красному при тех же условиях критического выставления, если цель неочевидна. Используются версии и живые снимка номинации; текущая реализация использует накопленные до конца журнала проверки шерифа."),
    "sheriff_two_unobvious_black_checks": (0.2, "Шерифу один раз за две подряд чёрные проверки. Каждая цель в момент своей проверки не должна быть автором активной версии. Красная проверка или проверка автора сбрасывает серию; общий алгоритм очевидности здесь не применяется."),
    "don_missed_sheriff_two_checks": (-0.1, "Дону один раз, если он выполнил проверки именно в первую и вторую ночь и ни одна не нашла шерифа. Пропущенная ночь не заменяется третьей; поздняя находка штраф не снимает. Номер ночи — day события."),
    "citizen_false_check": (-0.1, "Только обычному мирному один раз за игру за фактически неверный цвет в любой сохранённой публичной версии. Исправление или удаление версии штраф не отменяет; шериф считается красным."),
    "sheriff_false_check_black_win": (-0.5, "Шерифу один раз при итоговой победе чёрных за фактически неверный цвет в последней активной версии. Проверять цель на самом деле не обязательно. Исправленная/удалённая ложь не штрафуется."),
    "black_day_under_seven": (0.1, "Каждому живому чёрному за наступление дня с 3–6 живыми включительно. При двух и менее или семи и более начислений нет. Мёртвые не получают; повтор номера дня отдельно не проверяется."),
    "night_opinion_correct": (0.1, "За каждый фактически верный цвет красного автора ночного мнения, кроме совпадения ответа с очевидным цветом. Противоположный очевидному ответ оценивается по факту, а не автоматически как ошибка."),
    "night_opinion_wrong": (-0.1, "За каждый фактически неверный цвет красного автора ночного мнения, кроме совпадения ответа с очевидным цветом. Чёрные авторы и мнение о себе исключены."),
    "night_opinion_black_named_red": (0.05, "Чёрной цели за каждый ответ красного автора «красный», если ответ не совпал с очевидным для автора цветом. Может сочетаться со штрафом автору."),
    "farewell_red_correct": (0.15, "Красному автору завещания за фактически красную цель, оставленную красной, кроме совпадения с очевидным цветом."),
    "farewell_red_wrong": (-0.2, "Красному автору завещания за фактически красную цель, оставленную чёрной, кроме совпадения с очевидным цветом."),
    "farewell_black_correct": (0.2, "Красному автору завещания за фактически чёрную цель, оставленную чёрной, кроме совпадения с очевидным цветом."),
    "farewell_black_wrong": (-0.25, "Красному автору завещания за фактически чёрную цель, оставленную красной, кроме совпадения с очевидным цветом."),
    "farewell_black_named_red": (0.1, "Чёрной цели, не являющейся автором версии снимка, за каждое завещание красного «красный», прошедшее фильтр очевидности. Все цвета используют общий context завершения речи."),
    "farewell_claimant_black_named_red": (0.15, "Чёрной цели — автору активной версии снимка — за завещание красного «красный», прошедшее фильтр очевидности. Заменяет обычный бонус цели, не складывается с ним; используется общий context завещания."),
}
DEFAULTS = build_game_scoring_rules_snapshot()
CASES = []


def v(actor, *checks):
    return {"claimant_id": actor, "checks": [
        {"target_id": target, "verdict": color} for target, color in checks
    ]}


def death(target, **fields):
    return {"type": "death", "target_id": target, **fields}


def score(actions, result="draw", rules=None, mode="rating"):
    args = dict(mode=mode, result=result, roles=ROLES, player_ids=IDS,
                actions=actions, scoring_rules=DEFAULTS if rules is None else rules)
    return calculate_game_points(**args), calculate_game_points_breakdown(**args)


def isolated_rules(key, value=None):
    rules = dict(DEFAULTS)
    for name in RULE_SPECS:
        if name not in BOUNDS:
            rules[name] = 0
    rules[key] = RULE_SPECS[key][0] if value is None else value
    return rules


def add_case(key, actions, deltas, negative, result="draw"):
    CASES.append((key, copy.deepcopy(actions), dict(deltas),
                  copy.deepcopy(negative), result))


for key, lost in (("fourth_foul", False), ("fourth_foul_lost", True)):
    add_case(key, [dict(type="foul", target_id=2, count=4),
                  death(2, reason="foul", game_lost_after=lost)],
             {2: RULE_SPECS[key][0]}, [dict(type="foul", target_id=2, count=3)])
add_case("tech_foul", [dict(type="tech_foul", target_id=2, count=1)], {2: -0.15},
         [dict(type="tech_foul", target_id=2, count=0)])
add_case("second_tech_foul_lost", [dict(type="tech_foul", target_id=2, count=2),
         death(2, reason="foul", game_lost_after=True)], {2: -0.35},
         [dict(type="tech_foul", target_id=2, count=2), death(2, reason="foul", game_lost_after=False)])
for key, lost in (("suicide", False), ("suicide_lost", True)):
    add_case(key, [death(2, reason="suicide", game_lost_after=lost)],
             {2: RULE_SPECS[key][0]}, [death(2, reason="night")])
for count in range(4):
    key = f"best_move_black_{count}"
    targets = [8, 9, 10][:count] + [3, 4, 5][:3-count]
    add_case(key, [dict(type="best_move", actor_id=2, targets=targets)],
             {2: RULE_SPECS[key][0]}, [dict(type="best_move", actor_id=8, targets=targets)])
for key, terminal in (("night_shoot_miss", False), ("night_shoot_miss_terminal", True)):
    event = dict(type="night_shoot_result", kill_ok=False, shooters=[8, 9, 10],
                 shots={"8": 2, "9": 2, "10": 3}, black_wins_if_kill=terminal)
    add_case(key, [event], {10: RULE_SPECS[key][0]},
             [{**event, "shots": {"8": 2, "9": 3, "10": 4}}])
for night in (1, 2):
    key = f"night_self_shot_black_win_{night}"
    event = dict(type="night_shoot_result", day=night, kill_ok=True, kill_uid=8)
    add_case(key, [event], {8: RULE_SPECS[key][0]}, [{**event, "kill_uid": 2}], "black")
event = dict(type="vote", day=2, leaders=[8], targets=[8], will_eliminate=True, votes={"8": [2]})
add_case("vote_opponent_team", [event, death(8, reason="vote", day=2)], {2: 0.15},
         [{**event, "will_eliminate": False}])
add_case("vote_red_day_one_compensation", [death(2, reason="vote", day=1, vote_unique=True)],
         {2: 0.15}, [death(2, reason="vote", day=2, vote_unique=True)])
for key, count in (("vote_red_terminal", 2), ("vote_red_terminal_3v3", 3)):
    event = death(3, reason="vote", day=2, vote_unique=True, by=[2], result_after="black",
                  red_alive_after=count, black_alive_after=count)
    add_case(key, [event], {2: RULE_SPECS[key][0]}, [{**event, "vote_lift": True}], "black")
events = [death(uid, reason="night") for uid in (4, 5, 6, 7)]
add_case("black_win_3v3", events, {8: 0.3, 9: 0.3, 10: 0.3}, events[:-1], "black")
events = [death(uid, reason="night") for uid in (10, 3, 4, 5, 6, 7)]
add_case("black_win_2v2_1v1_alive", events, {8: 0.2, 9: 0.2}, [death(3, reason="night")], "black")
add_case("black_win_2v2_1v1_dead", events, {10: 0.1}, [death(3, reason="night")], "black")
for key, actor in (("vote_lift_same_team", 8), ("vote_lift_opponent_team", 2)):
    event = dict(type="vote", lift=True, passed=True, targets=[8, 9], by=[actor])
    add_case(key, [event], {actor: RULE_SPECS[key][0]}, [{**event, "passed": False}])
for key, actor in (("nomination_black_prevents_black_win", 10), ("nomination_red_last_hope", 2)):
    alive = [1, 2, 3, 4, 5, 8, 9, 10]
    events = [dict(type="nominate", day=2, actor_id=actor, target_id=8,
                   scoring_context={"alive": alive, "versions": [], "speakers_after": []}),
              dict(type="vote", day=2, targets=[3, 8], alive=alive), death(8, reason="vote", day=2)]
    negative = copy.deepcopy(events)
    negative[0]["scoring_context"]["speakers_after"] = [4]
    add_case(key, events, {actor: RULE_SPECS[key][0]}, negative)
add_case("sheriff_two_unobvious_black_checks",
         [dict(type="night_check", actor_id=1, target_id=t) for t in (8, 9)], {1: 0.2},
         [dict(type="night_check", actor_id=1, target_id=t) for t in (8, 2)])
add_case("don_missed_sheriff_two_checks",
         [dict(type="night_check", actor_id=10, target_id=t, day=n) for n, t in enumerate((2, 3), 1)], {10: -0.1},
         [dict(type="night_check", actor_id=10, target_id=t, day=n) for n, t in enumerate((2, 1), 1)])
add_case("citizen_false_check", [dict(type="versions", versions=[v(2, (8, "red"))])], {2: -0.1},
         [dict(type="versions", versions=[v(2, (8, "black"))])])
add_case("sheriff_false_check_black_win", [dict(type="versions", versions=[v(1, (8, "red"))])], {1: -0.5},
         [dict(type="versions", versions=[v(1, (8, "black"))])], "black")
add_case("black_day_under_seven", [dict(type="day_start", alive=[1, 2, 3, 4, 8, 9])], {8: 0.1, 9: 0.1},
         [dict(type="day_start", alive=[1, 2, 3, 4, 5, 8, 9])])
add_case("night_opinion_correct", [dict(type="night_opinions", opinions={2: {3: "red"}})], {2: 0.1},
         [dict(type="night_opinions", opinions={2: {3: "black"}})])
for key, recipient in (("night_opinion_wrong", 2), ("night_opinion_black_named_red", 8)):
    add_case(key, [dict(type="night_opinions", opinions={2: {8: "red"}})], {recipient: RULE_SPECS[key][0]},
             [dict(type="night_opinions", opinions={2: {8: "black"}})])
for key, target, guess in (("farewell_red_correct", 3, "red"), ("farewell_red_wrong", 3, "black"),
                           ("farewell_black_correct", 8, "black"), ("farewell_black_wrong", 8, "red"),
                           ("farewell_black_named_red", 8, "red"), ("farewell_claimant_black_named_red", 8, "red")):
    versions = [v(8, (3, "red")), v(9, (4, "red"))] if "claimant" in key else []
    event = dict(type="farewell", actor_id=2, wills={target: guess}, context={"versions": versions, "alive": IDS})
    recipient = 8 if "named_red" in key else 2
    add_case(key, [event], {recipient: RULE_SPECS[key][0]}, [{**event, "actor_id": 10}])


def marked_break_actions(key, actor, target):
    actions = [dict(type="versions", versions=[], scoring_marks={key: actor}),
               death(target, reason="vote", day=1, vote_unique=True, by=[actor]),
               dict(type="day_start", day=2, alive=[uid for uid in IDS if uid != target])]
    if key == "vote_break_red_to_red":
        actions.append(death(actor, reason="vote", day=2, vote_unique=True))
    return actions


for key, actor, target in (("vote_break_red_to_red", 2, 3),
                           ("vote_break_red_to_black", 2, 8),
                           ("vote_break_black_to_sheriff", 8, 1)):
    actions = marked_break_actions(key, actor, target)
    negative = copy.deepcopy(actions)
    negative[1]["by"] = []
    add_case(key, actions, {actor: RULE_SPECS[key][0]}, negative)


class ScoringRulesTests(unittest.TestCase):
    maxDiff = None

    def test_every_parameter_has_description_and_test(self):
        """Новый параметр требует русского описания, ставки и двух сценариев."""
        self.assertEqual(set(RULE_SPECS), set(GAME_SCORING_RULE_DEFAULTS))
        self.assertEqual({row[0] for row in CASES}, set(RULE_SPECS) - BOUNDS)
        self.assertEqual(len(CASES), len(RULE_SPECS) - len(BOUNDS))
        for key, (value, description) in RULE_SPECS.items():
            with self.subTest(rule=key):
                self.assertTrue(any("а" <= letter.lower() <= "я" for letter in description))
                self.assertEqual(Decimal(str(value)), GAME_SCORING_RULE_DEFAULTS[key])

    def test_base_and_normal_mode(self):
        """База: победа +1, поражение/ничья 0. Обычная игра не имеет баллов и аудита."""
        for result in ("red", "black", "draw"):
            points, breakdown = score([], result)
            for uid in IDS:
                expected = int((result == "red" and uid <= 7) or (result == "black" and uid >= 8))
                self.assertEqual(points[str(uid)], expected)
                self.assertEqual(breakdown[str(uid)]["final_points"], expected)
            actions = [dict(type="tech_foul", target_id=2, count=1)]
            self.assertEqual(score(actions, result, mode="normal"), ({}, {}))
            self.assertEqual(calculate_game_scoring_audit(mode="normal", result=result,
                roles=ROLES, player_ids=IDS, actions=actions, scoring_rules=DEFAULTS), [])

    def test_additional_points_min(self):
        """Минимум ограничивает сумму разных допов до базы; админ может изменить границу."""
        actions = [dict(type="tech_foul", target_id=2, count=1), death(2, reason="suicide", game_lost_after=True)]
        rules = dict(DEFAULTS, tech_foul=-0.8, suicide_lost=-0.7)
        points, breakdown = score(actions, "red", rules)
        self.assertEqual(breakdown["2"]["additional_points_raw"], -1.5)
        self.assertEqual(breakdown["2"]["additional_points"], -1)
        self.assertTrue(breakdown["2"]["additional_points_capped"])
        self.assertEqual(points["2"], 0)
        rules["additional_points_min"] = -2
        self.assertEqual(score(actions, "red", rules)[0]["2"], -0.5)
        self.assertEqual(score([], rules=dict(DEFAULTS, additional_points_min=0.5))[0]["2"], 0.5)

    def test_additional_points_max(self):
        """Максимум ограничивает сумму разных допов до базы; допускается предел больше +1."""
        actions = [dict(type="best_move", actor_id=2, targets=[8, 9, 10]),
                   dict(type="night_opinions", opinions={2: {3: "red"}})]
        rules = dict(DEFAULTS, best_move_black_3=0.8, night_opinion_correct=0.7)
        points, breakdown = score(actions, "red", rules)
        self.assertEqual(breakdown["2"]["additional_points_raw"], 1.5)
        self.assertEqual(breakdown["2"]["additional_points"], 1)
        self.assertTrue(breakdown["2"]["additional_points_capped"])
        self.assertEqual(points["2"], 2)
        rules["additional_points_max"] = 2
        self.assertEqual(score(actions, "red", rules)[0]["2"], 2.5)

    def test_obvious_answer_filter(self):
        """Ответ, совпавший с очевидным цветом, исключён; противоположный оценивается вместе с бонусом цели."""
        for kind, penalty, bonus in (("night_opinions", -0.1, 0.05), ("farewell", -0.25, 0.1)):
            for guess in ("black", "red"):
                with self.subTest(kind=kind, guess=guess):
                    event = (dict(type=kind, opinions={1: {8: guess}}) if kind == "night_opinions"
                             else dict(type=kind, actor_id=1, wills={8: guess}))
                    points, _ = score([dict(type="night_check", actor_id=1, target_id=8), event])
                    self.assertEqual(points["1"], penalty if guess == "red" else 0)
                    self.assertEqual(points["8"], bonus if guess == "red" else 0)

    def test_farewell_shared_context(self):
        """Все отметки завещания используют общий context завершения речи, а не прежние версии."""
        actions = [dict(type="versions", versions=[]), dict(type="farewell", actor_id=2,
            wills={3: "red", 4: "red"},
            context={"versions": [v(1, (3, "red"), (4, "red"))], "alive": IDS})]
        self.assertEqual(score(actions)[0]["2"], 0)
        actions[-1]["context"]["versions"] = []
        self.assertEqual(score(actions)[0]["2"], 0.3)

    def test_miss_counts_and_replacement(self):
        """Двое не штрафуются, одиночка только на победу, виновник из троих получает одну ставку."""
        for shooters, shots, terminal, expected in (
            ([8], {}, False, {}), ([8], {}, True, {8: -0.5}),
            ([8, 9], {"8": 2, "9": 3}, True, {}),
            ([8, 9, 10], {"8": 2, "9": 2}, False, {10: -0.2}),
            ([8, 9, 10], {"8": 2, "9": 2}, True, {10: -0.5}),
            ([8, 9, 10], {"8": 2, "9": 3, "10": 4}, True, {}),
        ):
            with self.subTest(shooters=shooters, shots=shots, terminal=terminal):
                points, _ = score([dict(type="night_shoot_result", kill_ok=False,
                    shooters=shooters, shots=shots, black_wins_if_kill=terminal)])
                self.assertEqual(points, {str(uid): expected.get(uid, 0) for uid in IDS})

    def test_nomination_disabled_at_four_players(self):
        """Оба правила выставлений отключены при четырёх живых даже на критическом столе."""
        for key, actor in (("nomination_red_last_hope", 2), ("nomination_black_prevents_black_win", 8)):
            alive = [1, 2, 3, 8]
            events = [dict(type="nominate", actor_id=actor, target_id=8, day=2,
                          scoring_context={"alive": alive, "versions": [], "speakers_after": []}),
                      dict(type="vote", day=2, targets=[3, 8], alive=alive), death(8, reason="vote", day=2)]
            self.assertEqual(score(events, rules=isolated_rules(key))[0][str(actor)], 0)

    def test_technical_fouls_accumulate(self):
        """Первый техфол сохраняется: два обычных дают -0.30, повышенный второй даёт суммарно -0.50."""
        actions = [dict(type="tech_foul", target_id=2, count=n) for n in (1, 2)]
        self.assertEqual(score(actions)[0]["2"], -0.3)
        actions.append(death(2, reason="foul", game_lost_after=True))
        self.assertEqual(score(actions)[0]["2"], -0.5)

    def test_checks_once_and_version_corrections(self):
        """Штрафы/бонусы проверок однократны; отменённая ложь мирного остаётся, шерифа исчезает."""
        actions = [dict(type="night_check", actor_id=1, target_id=t) for t in (8, 9, 10)]
        self.assertEqual(score(actions)[0]["1"], 0.2)
        actions = [dict(type="night_check", actor_id=10, target_id=t, day=n) for n, t in enumerate((2, 3, 1), 1)]
        self.assertEqual(score(actions)[0]["10"], -0.1)
        self.assertEqual(score(actions[:1])[0]["10"], 0)
        for actor, expected in ((2, 0.9), (1, 1)):
            actions = [dict(type="versions", versions=[v(actor, (8, "red"), (9, "red"))]),
                       dict(type="versions", versions=[])]
            # Победа красных: штраф мирного остаётся, шериф не штрафуется.
            self.assertEqual(score(actions, "red")[0][str(actor)], expected)
            self.assertEqual(score(actions, "black")[0][str(actor)], -0.1 if actor == 2 else 0)

    def test_self_shot_requires_final_black_win(self):
        """Компенсация самострела только в ночи 1/2 и при финальной победе чёрных."""
        for night in (1, 2, 3):
            for result in ("red", "black"):
                points, _ = score([dict(type="night_shoot_result", day=night, kill_ok=True, kill_uid=8)], result)
                extra = {1: 0.25, 2: 0.15}.get(night, 0) if result == "black" else 0
                self.assertEqual(points["8"], (1 if result == "black" else 0) + extra)

    def test_claimant_bonus_replaces_ordinary_bonus(self):
        """За красное завещание чёрному автору версии +0.15 вместо +0.10; автору завещания -0.25."""
        points, _ = score([dict(type="farewell", actor_id=2, wills={8: "red"},
            context={"versions": [v(8, (3, "red")), v(9, (4, "red"))], "alive": IDS})])
        self.assertEqual(points["8"], 0.15)
        self.assertEqual(points["2"], -0.25)

    def test_best_move_deduplicates_targets(self):
        """Повтор одной чёрной цели считается один раз; пустой лучший ход считается нулём чёрных."""
        rules = dict(DEFAULTS, best_move_black_1=0.37)
        self.assertEqual(score([dict(type="best_move", actor_id=2, targets=[8, 8, 8])], rules=rules)[0]["2"], 0.37)
        self.assertEqual(score([dict(type="best_move", actor_id=2, targets=[])])[0]["2"], -0.1)

    def test_settings_snapshot(self):
        """Сформированный снимок чисел и подписей не меняется при изменении исходных настроек."""
        settings = dict(night_opinion_correct=0.1, night_opinion_correct_label="Старая подпись")
        old = build_game_scoring_rules_snapshot(settings)
        settings.update(night_opinion_correct=0.7, night_opinion_correct_label="Новая подпись")
        new = build_game_scoring_rules_snapshot(settings)
        actions = [dict(type="night_opinions", opinions={2: {3: "red"}})]
        for rules, expected, label in ((old, 0.1, "Старая подпись"), (new, 0.7, "Новая подпись")):
            points, breakdown = score(actions, rules=rules)
            self.assertEqual(points["2"], expected)
            self.assertEqual(breakdown["2"]["adjustments"][0]["label"], label)

    def test_rounding(self):
        """Округление до сотых ROUND_HALF_UP для положительных и отрицательных чисел."""
        for raw, expected in ((1, 1.0), (0.1, 0.1), (0.125, 0.13), (-0.125, -0.13), (0.124, 0.12)):
            self.assertEqual(normalize_game_points_value(raw), expected)

    def test_vote_break_marks_validate(self):
        """Принимаются только одиночные ID игроков; ведущего, неизвестные ключи и некорректные значения отклоняем."""
        key = "vote_break_red_to_red"
        for raw in ([], {key: [2]}, {key: True}, {key: 11}, {key: -1}, {key: "2"}, {"unknown": 2}):
            with self.subTest(raw=raw):
                self.assertIsNone(parse_game_scoring_marks(raw, IDS))
        self.assertEqual(parse_game_scoring_marks({key: 2}, IDS)[key], 2)
        self.assertEqual(parse_game_scoring_marks({}, IDS)[key], 0)

    def test_vote_break_conditions_and_latest_selection(self):
        """Роль, первый день, голос, отсутствие подъёма и последняя отметка обязательны; повтор отметки не удваивает балл."""
        for key, actor, target in (("vote_break_red_to_red", 2, 3),
                                   ("vote_break_red_to_black", 2, 8),
                                   ("vote_break_black_to_sheriff", 8, 1)):
            rules = isolated_rules(key)
            original = marked_break_actions(key, actor, target)
            for changes in ({"day": 2}, {"vote_lift": True}, {"vote_unique": False},
                            {"reason": "foul"}, {"target_id": 9 if target != 8 else 3}):
                actions = copy.deepcopy(original)
                actions[1].update(changes)
                self.assertEqual(score(actions, rules=rules)[0][str(actor)], 0, (key, changes))
            self.assertEqual(score(original[1:], rules=rules)[0][str(actor)], 0)
            # Любое сохранённое снятие отметки отменяет её; повтор сохранения не дублирует начисление.
            self.assertEqual(score(original + [original[0]], rules=rules)[0][str(actor)], RULE_SPECS[key][0])
            self.assertEqual(score(original + [dict(type="versions", versions=[], scoring_marks={})], rules=rules)[0][str(actor)], 0)
            replacement = 4 if actor == 2 else 9
            changed = original + [dict(type="versions", versions=[], scoring_marks={key: replacement})]
            self.assertEqual(score(changed, rules=rules)[0][str(actor)], 0)
            self.assertEqual(score(original, mode="normal", rules=rules), ({}, {}))

    def test_vote_break_second_day(self):
        """Голосование красного в красного требует единственного ухода во второй день; красного в чёрного исключает любой vote-уход."""
        key = "vote_break_red_to_red"
        actions = marked_break_actions(key, 2, 3)
        for changes in ({"day": 3}, {"vote_lift": True}, {"vote_unique": False}, {"reason": "night"}):
            changed = copy.deepcopy(actions)
            changed[-1].update(changes)
            self.assertEqual(score(changed, rules=isolated_rules(key))[0]["2"], 0)
        key = "vote_break_red_to_black"
        actions = marked_break_actions(key, 2, 8)
        self.assertEqual(score(actions[:2], rules=isolated_rules(key))[0]["2"], 0)
        for lift in (False, True):
            self.assertEqual(score(actions + [death(2, reason="vote", day=2, vote_lift=lift)], rules=isolated_rules(key))[0]["2"], 0)
        self.assertEqual(score(actions + [death(2, reason="night", day=1)], rules=isolated_rules(key))[0]["2"], 0.2)

    def test_red_to_black_break_cancelled_by_early_removal(self):
        """Удаление по фолам/техфолам и самоубийство в день 1/2 отменяют бонус; отстрел, день 3 и фол без ухода не отменяют."""
        key = "vote_break_red_to_black"
        rules = isolated_rules(key)
        base = marked_break_actions(key, 2, 8)
        for day in (1, 2, 3):
            for kind, count, reason in (("foul", 4, "foul"), ("tech_foul", 2, "foul"),
                                        (None, 0, "suicide"), (None, 0, "night")):
                with self.subTest(day=day, kind=kind, reason=reason):
                    removals = []
                    if kind:
                        removals.append(dict(type=kind, target_id=2, count=count, day=day))
                    removals.append(death(2, reason=reason, day=day))
                    actions = copy.deepcopy(base)
                    if day == 1:
                        actions[2]["alive"].remove(2)
                        actions[2:2] = removals
                    else:
                        actions.extend(removals)
                    expected = 0 if day in (1, 2) and reason in ("foul", "suicide") else 0.2
                    points, breakdown = score(actions, rules=rules)
                    self.assertEqual(points["2"], expected)
                    entries = [item for item in breakdown["2"]["adjustments"] if item["rule_key"] == key]
                    self.assertEqual(len(entries), int(expected != 0))
        for kind in ("foul", "tech_foul"):
            self.assertEqual(score(base + [dict(type=kind, target_id=2, count=1, day=2)], rules=rules)[0]["2"], 0.2)

    def test_red_vote_break_early_removals(self):
        """Фолы, техфолы и самоубийство в день 1/2 заменяют уход на голосовании; ночь, день 3 и один фол без удаления не подходят."""
        key = "vote_break_red_to_red"
        rules = isolated_rules(key)
        base = marked_break_actions(key, 2, 3)[:2]
        for day in (1, 2, 3):
            for kind, count, reason in (("foul", 4, "foul"), ("tech_foul", 2, "foul"),
                                        (None, 0, "suicide"), (None, 0, "night")):
                with self.subTest(day=day, kind=kind, reason=reason):
                    actions = copy.deepcopy(base)
                    if day >= 2:
                        actions.append(dict(type="day_start", day=2, alive=[1, 2, 4, 5, 6, 7, 8, 9, 10]))
                    if kind:
                        actions.append(dict(type=kind, target_id=2, count=count, day=day))
                    actions.append(death(2, reason=reason, day=day))
                    expected = -0.5 if day in (1, 2) and reason in ("foul", "suicide") else 0
                    points, breakdown = score(actions, rules=rules)
                    self.assertEqual(points["2"], expected)
                    entries = [item for item in breakdown["2"]["adjustments"] if item["rule_key"] == key]
                    self.assertEqual(len(entries), int(expected != 0))
        self.assertEqual(score(base + [dict(type="tech_foul", target_id=2, count=1, day=1)], rules=rules)[0]["2"], 0)
        # Отдельный штраф самоубийства сохраняется и складывается со сломом.
        actions = base + [death(2, reason="suicide", day=1)]
        self.assertEqual(score(actions)[0]["2"], -0.8)
        # Без исходного голоса за красного даже ранний уход не даёт штрафа слома.
        actions[1]["by"] = []
        self.assertEqual(score(actions, rules=rules)[0]["2"], 0)

    def test_vote_break_roles_and_audit(self):
        """Неверная команда автора исключает начисление; аудит привязан к последней отметке и объясняет отказ."""
        for key, actor, target in (("vote_break_red_to_red", 8, 3),
                                   ("vote_break_red_to_black", 9, 8),
                                   ("vote_break_black_to_sheriff", 2, 1)):
            actions = marked_break_actions(key, actor, target)
            rules = isolated_rules(key)
            self.assertEqual(score(actions, rules=rules)[0][str(actor)], 0)
            audit = calculate_game_scoring_audit(mode="rating", roles=ROLES, player_ids=IDS,
                actions=actions, scoring_rules=rules)
            item = next(item for item in audit if item["type"] == "marked_vote_break")
            self.assertEqual(item["reason"], "wrong_team")
            self.assertNotIn("actor_adjustment", item)
        key = "vote_break_black_to_sheriff"
        actions = marked_break_actions(key, 8, 1)[:2]  # Второй день этому правилу не нужен.
        actions.append(copy.deepcopy(actions[0]))
        audit = calculate_game_scoring_audit(mode="rating", roles=ROLES, player_ids=IDS,
            actions=actions, scoring_rules=isolated_rules(key))
        items = [item for item in audit if item["type"] == "marked_vote_break"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["action_order"], 3)
        self.assertEqual(items[0]["actor_adjustment"]["points"], 0.2)

    def test_black_victory_bonus_for_every_departure_reason(self):
        """Любой способ достижения итоговых 3в3/2в2/1в1 даёт один бонус; проигрыш/ничья не дают."""
        keys = ("black_win_3v3", "black_win_2v2_1v1_alive", "black_win_2v2_1v1_dead")
        rules = isolated_rules("black_win_3v3")
        for key in keys:
            rules[key] = RULE_SPECS[key][0]
        for count in (1, 2, 3):
            alive = set(range(1, count + 1)) | set(range(8, 8 + count))
            departed = [uid for uid in IDS if uid not in alive]
            for reason in ("night", "vote", "foul", "suicide"):
                for result in ("red", "black", "draw"):
                    with self.subTest(count=count, reason=reason, result=result):
                        actions = [death(uid, reason=reason) for uid in departed]
                        points, breakdown = score(actions, result, rules)
                        for uid in (8, 9, 10):
                            extra = (0.3 if count == 3 else 0.2 if uid in alive else 0.1) if result == "black" else 0
                            self.assertEqual(points[str(uid)], (1 if result == "black" else 0) + extra)
                            bonuses = [item for item in breakdown[str(uid)]["adjustments"] if item["rule_key"] in keys]
                            self.assertEqual(len(bonuses), int(result == "black"))

    def test_mass_departure_uses_final_composition(self):
        """Промежуточные 3в3 или 2в2 в подъёме не дают отдельного бонуса; порядок уходов не влияет."""
        rules = isolated_rules("black_win_3v3")
        rules.update(black_win_2v2_1v1_alive=0.2, black_win_2v2_1v1_dead=0.1)
        # Перед подъёмом 4 красных / 3 чёрных. После группы: 2 красных / 2 чёрных.
        prefix = [death(uid, reason="night") for uid in (5, 6, 7)]
        for group in ((3, 4, 10), (10, 4, 3), (4, 10, 3)):
            with self.subTest(group=group):
                actions = prefix + [death(uid, reason="vote", vote_lift=True,
                    result_after="black", red_alive_after=3, black_alive_after=3) for uid in group]
                points, _ = score(actions, "black", rules)
                self.assertEqual([points[str(uid)] for uid in (8, 9, 10)], [1.2, 1.2, 1.1])
        # Промежуточное 2в2, затем 2в1: даже ручной итог black не превращает стол в равенство.
        actions = [death(uid, reason="night") for uid in (4, 5, 6, 7, 10)]
        actions += [death(3, reason="vote", result_after="black", red_alive_after=2, black_alive_after=2),
                    death(8, reason="vote")]
        self.assertEqual([score(actions, "black", rules)[0][str(uid)] for uid in (8, 9, 10)], [1, 1, 1])

    def test_day_bonus_both_boundaries_and_repetition(self):
        """Дни с 3, 4, 5, 6 живыми оцениваются каждый раз; 0–2 и 7–10 исключены."""
        for count in range(11):
            alive = ([8] + [uid for uid in IDS if uid != 8])[:count]
            actions = [dict(type="day_start", day=day, alive=alive) for day in (2, 3)]
            points, _ = score(actions)
            self.assertEqual(points["8"], 0.2 if 2 < count < 7 else 0)
            if 9 not in alive:
                self.assertEqual(points["9"], 0)

    def test_don_checks_must_be_in_nights_one_and_two(self):
        """Проверки ночей 2/3, 1/3, без номера и повтор одной ночи не заменяют две стартовые ночи."""
        for checks, expected in (
            (((1, 2), (2, 3)), -0.1),
            (((1, 2), (2, 3), (3, 1)), -0.1),
            (((2, 2), (3, 3)), 0), (((1, 2), (3, 3)), 0),
            (((1, 2),), 0), (((2, 2),), 0), (((0, 2), (0, 3)), 0),
            (((1, 2), (1, 3)), 0), (((1, 1), (2, 3)), 0), (((1, 2), (2, 1)), 0),
        ):
            with self.subTest(checks=checks):
                actions = [dict(type="night_check", actor_id=10, target_id=uid, day=night) for night, uid in checks]
                self.assertEqual(score(actions)[0]["10"], expected)


def make_rule_test(row, positive):
    key, actions, deltas, negative, result = row

    def test(self):
        for custom in (False, True):
            with self.subTest(custom_setting=custom):
                value = 0.37 if custom else RULE_SPECS[key][0]
                rules = isolated_rules(key, value)
                label = "Проверочная подпись " + key
                if custom:
                    rules[key + "_label"] = label
                points, breakdown = score(copy.deepcopy(actions if positive else negative), result, rules)
                expected_deltas = ({uid: value for uid in deltas} if custom else deltas) if positive else {}
                for uid in IDS:
                    base = int((result == "red" and uid <= 7) or (result == "black" and uid >= 8))
                    expected = round(base + expected_deltas.get(uid, 0), 2)
                    self.assertEqual(points[str(uid)], expected, (key, uid))
                    self.assertEqual(breakdown[str(uid)]["final_points"], expected)
                    entries = [item for item in breakdown[str(uid)]["adjustments"] if item["rule_key"] == key]
                    should_apply = positive and uid in deltas
                    self.assertEqual(len(entries), int(should_apply), (key, uid, entries))
                    if should_apply:
                        self.assertEqual(entries[0]["points"], value)
                        if custom:
                            self.assertEqual(entries[0]["label"], label)

    branch = "срабатывает" if positive else "не срабатывает в исключённом случае"
    test.__doc__ = RULE_SPECS[key][1] + " Проверка: " + branch + "."
    return test


for scenario in CASES:
    for is_positive in (True, False):
        suffix = "positive" if is_positive else "negative"
        setattr(ScoringRulesTests, "test_" + scenario[0] + "_" + suffix, make_rule_test(scenario, is_positive))
