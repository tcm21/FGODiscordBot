import configparser
import requests
import json
import interactions
from interactions import autodefer

configparser = configparser.ConfigParser()
configparser.read('env.config')
token = configparser.get('Auth', 'TOKEN')
bot = interactions.Client(token=token)

def get_servant(name: str) -> interactions.Embed:
    """Gets the servant info based on the search query.

    Args:
        name (str): Servant name

    Returns:
        interactions.Embed: An embed discord object containing the servant info.
    """
    response = requests.get("https://api.atlasacademy.io/nice/JP/servant/search?name=" + name)
    json_data = json.loads(response.text)
    skill1 = json_data[0].get('skills')[0].get('name')
    skill1desc = json_data[0].get('skills')[0].get('detail')
    skill2 = json_data[0].get('skills')[1].get('name')
    skill2desc = json_data[0].get('skills')[1].get('detail')
    skill3 = json_data[0].get('skills')[2].get('name')
    skill3desc = json_data[0].get('skills')[2].get('detail')
    embed = interactions.Embed(
        title="Servant Info",
        description="",
        color=interactions.Color.black()
    )
    embed.set_thumbnail(
        url=json_data[0]
            .get('extraAssets')
            .get('faces')
            .get('ascension')
            .get('1')
    )

    embed.add_field("Name", json_data[0].get('name'))
    embed.add_field("Rarity", "★"*json_data[0].get('rarity'))
    embed.add_field("Class", json_data[0].get('className'))
    embed.add_field(f"Skill 1: {skill1}", skill1desc);
    embed.add_field(f"Skill 2: {skill2}", skill2desc);
    embed.add_field(f"Skill 3: {skill3}", skill3desc);

    return embed

def get_functions(type: str, target: str = ""):
    """Gets all the effects (functions) with the specified effect.

    Args:
        type (str): Effect name
        target (str): Effect target

    Returns:
        A list of functions with the specified effect.
    """
    if type == "": return []
    targetQueryStr = ""
    if target != "": targetQueryStr = f"&targetType={target}"
    url = f"https://api.atlasacademy.io/basic/JP/function/search?reverse=true&reverseDepth=servant&type={type}{targetQueryStr}"
    response = requests.get(url)
    functions = json.loads(response.text)
    return functions

def get_skills_from_functions(functions, flag: str = "skill"):
    found_skills = []
    for function in functions:
        for skill in function.get('reverse').get('basic').get(flag):
            if skill.get('name') == "": continue
            servants = skill.get('reverse').get('basic').get('servant')
            servant_found = False
            for servant in servants:
                if (servant.get('name') == "" or
                    servant.get('type') == "servantEquip" or
                    servant.get('type') == "enemy"
                    ):
                    continue
                servant_found = True
            if servant_found:
                found_skills.append(skill)
    return found_skills

def get_skills_with_type(type: str, flag: str = "skill", target: str = ""):
    """Get a list of skills or NP with the selected effects.

    Args:
        type (str): Effect name,
        flag (str, optional): "skill" or "NP". Defaults to "skill".
        target (str): Effect target

    Returns:
        A list of skill objects with the specified effect.
    """
    if type == "": return None
    functions = get_functions(type, target)
    found_skills = get_skills_from_functions(functions, flag)
    return found_skills

def get_skills_with_buff(buffType: str = "", flag: str = "skill"):
    if buffType == "": return None
    url = f"https://api.atlasacademy.io/basic/JP/buff/search?reverse=true&reverseDepth=servant&reverseData=basic&type={buffType}"
    response = requests.get(url)
    buffs = json.loads(response.text)
    skills = []
    for buff in buffs:
        functions = buff.get("reverse").get("basic").get("function")
        skills.extend(get_skills_from_functions(functions, flag))

    return skills

def get_skills(type: str, type2: str = "", flag: str = "skill", target: str = "", buffType1: str = "", buffType2: str = ""):
    """Get skills or noble phantasms with the selected effects.

    Args:
        type (str): Effect 1
        type2 (str, optional): Effect 2 (Optional)
        flag (str, optional): "skill" for skills or "NP" for noble phantasm. Defaults to "skill".
        target (str): Effect target
        buffType1 (str): Buff effect 1 (only works if type is 'buff')
        buffType2 (str): Buff effect 2 (only works if type2 is 'buff')

    Returns:
        A list of servants who has skills/NP with the effects specified.
    """
    found_list_1 = get_skills_with_type(type, flag, target)
    found_list_2 = get_skills_with_type(type2, flag, target)
    found_buff_list1 = get_skills_with_buff(buffType1, flag)
    found_buff_list2 = get_skills_with_buff(buffType2, flag)
    matched_skills_list = common_elements(found_list_1, found_list_2, found_buff_list1, found_buff_list2)
    result_str = []

    embed = interactions.Embed(
        title="Search results",
        description="",
        color=interactions.Color.black()
    )

    embed.add_field("Type 1", fn_names_json.get(type), True)
    if type2 != "": embed.add_field("Type 2", fn_names_json.get(type2), True)
    if target != "": embed.add_field("Target", tg_names_json.get(target), True)
    if buffType1 != "": embed.add_field("Buff 1", buff_names_json.get(buffType1), True)
    if buffType2 != "": embed.add_field("Buff 2", buff_names_json.get(buffType2), True)

    maxLimit = 15
    count = 0
    for skill in matched_skills_list:
        result_str.append(f"・{skill.get('name')}\n")
        servants = skill.get('reverse').get('basic').get('servant')
        servantList = []
        for servant in servants:
            if count == maxLimit: break
            if servant.get('name') == "" or servant.get('type') == "servantEquip":
                continue
            servant_str = f"{servant.get('name')} {servant.get('className')}\n"
            if servant_str not in servantList:
                servantList.append(servant_str)
                embed.add_field(servant_str, f"[{skill.get('name')}](https://apps.atlasacademy.io/db/JP/{'skill' if flag == 'skill' else 'noble-phantasm'}/{skill.get('id')})")
                count+=1
                result_str.append(servant_str)

    if count > 0:
        return embed
    else:
        embed.add_field("Not found.", "Try different queries")
        return embed

def common_elements(*lists):
    common_list = []
    for list in lists:
        if list == None: continue
        if len(list) == 0: return []
        if len(common_list) == 0 and len(list) > 0:
            common_list.extend(list)
            continue
        common_list = [element for element in common_list if element in list]
    return common_list

# Commands
@bot.command(
    scope=[760776452609802250],
)
@interactions.option(str, name="name", description="Servant name", required=True)
async def servant(ctx: interactions.CommandContext, name: str):
    await ctx.send(embeds=get_servant(name))

@bot.command(
    scope=[760776452609802250],
)
@interactions.option(str, name="type", description="Effect 1", required=True, autocomplete=True)
@interactions.option(str, name="type2", description="Effect 2", required=False, autocomplete=True)
@interactions.option(str, name="target", description="Target", required=False, autocomplete=True)
@interactions.option(str, name="buff", description="Buff 1", required=False, autocomplete=True)
@interactions.option(str, name="buff2", description="Buff 2", required=False, autocomplete=True)
async def skill(
    ctx: interactions.CommandContext,
    type: str,
    type2: str = "",
    target: str = "",
    buff: str = "",
    buff2: str = "",
    ):
    await ctx.defer()
    embed = get_skills(type, type2, "skill", target, buff, buff2)
    await ctx.send(embeds=embed)

@bot.command(
    scope=[760776452609802250],
)
@interactions.option(str, name="type", description="Effect 1", required=True, autocomplete=True)
@interactions.option(str, name="type2", description="Effect 2", required=False, autocomplete=True)
@interactions.option(str, name="target", description="Target", required=False, autocomplete=True)
@interactions.option(str, name="buff", description="Buff 1", required=False, autocomplete=True)
@interactions.option(str, name="buff2", description="Buff 2", required=False, autocomplete=True)
async def np(
    ctx: interactions.CommandContext,
    type: str,
    type2: str = "",
    target: str = "",
    buff: str = "",
    buff2: str = "",
    ):
    await ctx.defer()
    embed = get_skills(type, type2, "NP", target, buff, buff2)
    await ctx.send(embeds=embed)

# Autocomplete functions
with open('function_names.json') as fn_names:
    fn_names_json = json.load(fn_names)

with open('target_names.json') as tg_names:
    tg_names_json = json.load(tg_names)

with open('buff_names.json') as buff_names:
    buff_names_json = json.load(buff_names)

def populateSkillNamesList(input_value: str):
    options = fn_names_json.keys()
    filteredOptions = [
        option for option in options
        if (input_value.upper() in option.upper() or input_value.upper() in fn_names_json.get(option, option).upper())
    ]
    choices = []
    for option in filteredOptions[0:24]:
        text = fn_names_json.get(option, option)
        choices.append(interactions.Choice(name=text, value=option))
    return choices

def populateTargetList(input_value: str):
    options = tg_names_json.keys()
    filteredOptions = [
        option for option in options
        if (input_value.upper() in option.upper() or input_value.upper() in tg_names_json.get(option, option).upper())
    ]
    choices = []
    for option in filteredOptions[0:24]:
        text = tg_names_json.get(option, option)
        choices.append(interactions.Choice(name=text, value=option))
    return choices

def populateBuffList(input_value: str):
    options = buff_names_json.keys()
    filteredOptions = [
        option for option in options
        if (input_value.upper() in option.upper() or input_value.upper() in buff_names_json.get(option, option).upper())
    ]
    choices = []
    for option in filteredOptions[0:24]:
        text = buff_names_json.get(option, option)
        choices.append(interactions.Choice(name=text, value=option))
    return choices

@bot.autocomplete(command="skill", name="type")
@bot.autocomplete(command="np", name="type")
async def autocomplete_choice_list(ctx: interactions.CommandContext, type: str = ""):
    await ctx.populate(populateSkillNamesList(type))

@bot.autocomplete(command="skill", name="type2")
@bot.autocomplete(command="np", name="type2")
async def autocomplete_choice_list(ctx: interactions.CommandContext, type2: str = ""):
    await ctx.populate(populateSkillNamesList(type2))

@bot.autocomplete(command="skill", name="target")
@bot.autocomplete(command="np", name="target")
async def autocomplete_choice_list(ctx: interactions.CommandContext, target: str = ""):
    await ctx.populate(populateTargetList(target))
    
@bot.autocomplete(command="skill", name="buff")
@bot.autocomplete(command="np", name="buff")
async def autocomplete_choice_list(ctx: interactions.CommandContext, buff: str = ""):
    await ctx.populate(populateBuffList(buff))

@bot.autocomplete(command="skill", name="buff2")
@bot.autocomplete(command="np", name="buff2")
async def autocomplete_choice_list(ctx: interactions.CommandContext, buff2: str = ""):
    await ctx.populate(populateBuffList(buff2))

bot.start()
