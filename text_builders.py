import requests_cache
import json
import re
from enum import Flag

SUB = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")

class NpFunctionType(Flag):
    LEVEL = 1
    OVERCHARGE = 2
    BOTH = LEVEL | OVERCHARGE
    NONE = 4


def get_np_function_type(function) -> NpFunctionType:
    svals = function.get("svals")
    svals2 = function.get("svals2")
    if (svals[0].get("Value") != svals[1].get("Value") and
        (svals[0].get("Value") != svals2[0].get("Value") or svals[0].get("Correction") != svals2[0].get("Correction"))
        ):
        return NpFunctionType.BOTH

    if svals[0].get("Value") != svals[1].get("Value"):
        return NpFunctionType.LEVEL
    
    if svals[0].get("Value") != svals2[0].get("Value") or svals[0].get("Correction") != svals2[0].get("Correction"):
        return NpFunctionType.OVERCHARGE
    
    return NpFunctionType.NONE


def get_skill_description(session: requests_cache.CachedSession, skill, sub_skill: bool = False):
    skill_descs = []
    if not sub_skill and skill.get("coolDown"): skill_descs.append(f'**Base Cooldown: ** {skill.get("coolDown")[0]}')
    is_np = False
    if skill.get("card"): is_np = True # Noble phantasms
    funcIdx = 0
    for function in skill.get("functions"):
        if function.get("funcTargetTeam") == "enemy": continue
        func_type = function.get("funcType")
        if func_type == "none": continue

        svals = function.get("svals")
        sval_rate = svals[0].get("Rate")
        sval_turns = svals[0].get("Turn")
        sval_count = svals[0].get("Count")
        sval_value = svals[0].get("Value")
        sval_userate = svals[0].get("UseRate")
        sval_target = svals[0].get("Target")

        chances_text = ""
        values_text = ""
        turns_text = ""
        count_text = ""
        usechance_text = ""
        supereffective_target = ""
        target_vals_text = ""

        np_function_type = NpFunctionType.NONE
        if is_np: np_function_type = get_np_function_type(function)

        func_tvals = function.get("functvals")
        if func_tvals:
            target_traits = []
            for tval in func_tvals:
                if int(tval.get("id")) >= 5000: continue
                target_traits.append(get_trait_desc(session, tval.get("id")))
            target_vals_text = f' with trait [{", ".join(target_traits)}]'

        buff_type = function.get("buffs")[0].get("type") if function.get("buffs") and len(function.get("buffs")) > 0 else ""
        is_single_value = False
        if sval_value:
            valuesTextList = []
            if buff_type.endswith("Function"):
                func_skill = get_skill_by_id(session, sval_value)
                func_skill_desc = get_skill_description(session=session, skill=func_skill, sub_skill=True)
                values_text += func_skill_desc
            elif all(sval.get("Value") == svals[0].get("Value") for sval in svals):
                # All values are the same
                if is_np and NpFunctionType.OVERCHARGE in np_function_type:
                    values_text = get_overcharge_values(function, buff_type, func_type)
                else:
                    is_single_value = True
                    if buff_type == "addIndividuality":
                        values_text = f'{get_trait_desc(session, svals[0].get("Value"))}'
                    else:
                        values_text = f'{get_sval_from_buff(svals[0].get("Value"), buff_type, func_type)}'
            else:
                for svalIdx, sval in enumerate(svals):
                    valuesTextList.append(f'{get_sval_from_buff(sval.get("Value"), buff_type, func_type)}{str(svalIdx + 1).translate(SUB)}')
                np_text = " (Level)" if is_np and NpFunctionType.LEVEL in np_function_type else ""
                values_text = f'Value{np_text}: {" · ".join(valuesTextList)}'
                if is_np:
                    if sval_target and func_type == "damageNpIndividual":
                        supereffective_target = get_trait_desc(session, sval_target)
                    if NpFunctionType.OVERCHARGE in np_function_type:
                        values_text += "\n" + get_overcharge_values(function, buff_type, func_type, True)

        if sval_rate and sval_rate != 1000 and sval_rate != 5000:
            chances_list = []
            if all(sval.get("Rate") == svals[0].get("Rate") for sval in svals):
                # All values are the same
                chances_text = f'Chance: {remove_zeros_decimal(svals[0].get("Rate") / 10)}%'
            else:
                for svalIdx, sval in enumerate(svals):
                    chances_list.append(f'{remove_zeros_decimal(sval.get("Rate") / 10)}{str(svalIdx + 1).translate(SUB)}%')
                chances_text = f'Chance: {" · ".join(chances_list)}'

        if sval_userate and sval_userate != 1000 and sval_userate != 5000:
            usechances_list = []
            if all(sval.get("UseRate") == svals[0].get("UseRate") for sval in svals):
                usechance_text = f'Chance: {remove_zeros_decimal(svals[0].get("UseRate") / 10)}%'
            else:
                for svalIdx, sval in enumerate(svals):
                    usechances_list.append(f'{remove_zeros_decimal(sval.get("UseRate") / 10)}%{str(svalIdx + 1).translate(SUB)}%')
                usechance_text = f'Chance: {" · ".join(usechances_list)}'

        if sval_count and sval_count > 0:
            count_text = f'{sval_count} Times'
        if sval_turns and sval_turns > 0:
            turns_text = f'{sval_turns} Turns'

        turns_count_text = ", ".join([count_text, turns_text]).strip(", ")
        if turns_count_text: turns_count_text = f"({turns_count_text})"
        
        function_effect = function.get("funcPopupText")
        if not function_effect: function_effect = title_case(func_type)
        inline_value_text = f" ({values_text})" if is_single_value else ""

        sub_skill_text = "└Sub-" if sub_skill else ""
            
        if func_type == "damageNpIndividual":
            skill_descs.append(f'**{sub_skill_text}Effect {funcIdx + 1}**: Deals damage to [{title_case(function.get("funcTargetType"))}] with bonus damage to [{supereffective_target}]')
        elif func_type.startswith("damageNp"):
            skill_descs.append(f'**{sub_skill_text}Effect {funcIdx + 1}**: Deals damage to [{title_case(function.get("funcTargetType"))}]')
        elif func_type.startswith("addState"):
            function_effect = f'Grants [{title_case(buff_type)}]'

            func_quest_tvals = function.get("funcquestTvals") # Fields
            if func_quest_tvals:
                target_traits = []
                for tval in func_quest_tvals:
                    target_traits.append(title_case(tval.get("name")))
                if len(target_traits) > 0: function_effect += f' on [{", ".join(target_traits)}]'

            ck_self_indv = function.get("buffs")[0].get("ckSelfIndv") # Cards
            if ck_self_indv:
                target_traits = []
                for ck in ck_self_indv:
                    target_traits.append(title_case(ck.get("name")))
                if len(target_traits) > 0: function_effect += f' to [{", ".join(target_traits)}]'
            
            ck_op_indv = function.get("buffs")[0].get("ckOpIndv") # Atk bonus for trait
            if ck_op_indv:
                target_traits = []
                for ck in ck_op_indv:
                    if int(ck.get("id")) < 3000:
                        trait_desc = get_trait_desc(session, ck.get("id"))
                    else:
                        trait_desc = title_case(ck.get("name"))
                    target_traits.append(trait_desc)
                if len(target_traits) > 0: function_effect += f' against [{", ".join(target_traits)}]'

            skill_descs.append(f'**{sub_skill_text}Effect {funcIdx + 1}**: {function_effect}{inline_value_text} to [{title_case(function.get("funcTargetType"))}]{target_vals_text} {turns_count_text}')
        else:
            skill_descs.append(f'**{sub_skill_text}Effect {funcIdx + 1}**: {function_effect}{inline_value_text} to [{title_case(function.get("funcTargetType"))}]{target_vals_text} {turns_count_text}')

        if chances_text: skill_descs.append(f'{chances_text}')
        if usechance_text: skill_descs.append(f'{usechance_text}')
        if values_text and not is_single_value: skill_descs.append(f'{values_text}')
        funcIdx += 1
    return "\n".join(skill_descs)


def get_overcharge_values(function, buff_type, func_type, is_correction: bool = False):
    valuesTextList = []
    for svalIdx, sval in enumerate([
        function.get("svals")[0],
        function.get("svals2")[0],
        function.get("svals3")[0],
        function.get("svals4")[0],
        function.get("svals5")[0],
    ]):
        valuesTextList.append(f'{get_sval_from_buff(sval.get("Correction" if is_correction else "Value"), buff_type, func_type)}{str(svalIdx + 1).translate(SUB)}')
    values_text = f'Value (Overcharge): {" - ".join(valuesTextList)}'
    return values_text


def get_sval_from_buff(value: int, buff_type: str, func_type: str) -> str:
    if not buff_type:
        if func_type == "gainNp":
            return f'{remove_zeros_decimal(value / 100)}%'
        elif func_type.startswith("damageNp"):
            return f'{remove_zeros_decimal(value / 10)}%'
        elif func_type == "lossNp":
            return f'{remove_zeros_decimal(value / 100)}%'
    if buff_type == "upChagetd":
        return remove_zeros_decimal(value)
    if buff_type.startswith("up") or buff_type.startswith("down"):
        return f'{remove_zeros_decimal(value / 10)}%'
    if buff_type.startswith("regainNp"):
        return f'{remove_zeros_decimal(value / 100)}%'
    if buff_type.startswith("donotAct"):
        return f'{remove_zeros_decimal(value / 10)}%'
    return remove_zeros_decimal(value)


def remove_zeros_decimal(value):
    return str(value).rstrip("0").rstrip(".") if "." in str(value) else str(value)


def title_case(string):
    if not string:
        return
    words = re.sub('([A-Z][a-z]+)', r' \1', re.sub('([A-Z]+)', r' \1', string)).split()
    if len(words) > 0:
        words[0] = words[0][0].upper() + words[0][1:]
    return " ".join(words)


def get_trait_desc(session: requests_cache.CachedSession, trait_id: str | int):
    id = str(trait_id)
    trait_name = get_traits(session).get(id)
    trait_name = title_case(trait_name if trait_name else "unknown")
    if id.startswith("4"):
        # Cards
        return trait_name
    url = f'https://apps.atlasacademy.io/db/JP/entities?trait={id}'
    return f'[{trait_name}]({url})'


def get_skill_by_id(session: requests_cache.CachedSession, id: int, region: str = "JP"):
    """Get skill by ID

    Args:
        id (int): Skill ID
        region (str, optional): Region. Defaults to "JP".

    Returns:
        Skill object
    """
    response = session.get(
        f"https://api.atlasacademy.io/nice/{region}/skill/{id}")
    skill = json.loads(response.text)
    if skill.get('detail') == "Skill not found":
        return None
    else:
        return skill

def get_enums(session: requests_cache.CachedSession, enum_type: str):
    response = session.get(
        f"https://api.atlasacademy.io/export/JP/nice_enums.json")  # JP and NA use the same enums
    enums = json.loads(response.text)
    return enums.get(enum_type)


def get_traits(session: requests_cache.CachedSession):
    response = session.get(
        f"https://api.atlasacademy.io/export/JP/nice_trait.json")  # JP and NA use the same enums
    return json.loads(response.text)