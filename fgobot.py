import configparser
import json
import interactions
import requests_cache
import os
import re

from interactions.ext.paginator import Page, Paginator

token = os.environ.get("TOKEN")
if token == "" or token == None:
    configparser = configparser.ConfigParser()
    configparser.read('env.config')
    token = configparser.get('Auth', 'TOKEN')

bot = interactions.Client(
    token=token,
)

session = requests_cache.CachedSession()


def get_servant(name: str, cv_id: str, class_name: str, region: str = "JP") -> interactions.Embed:
    """Gets the servant info based on the search query.

    Args:
        name (str): Servant name
        region (str): Region (Default: JP)

    Returns:
        list: servants object
    """
    nameQuery = ""
    cvQuery = ""
    clsNameQuery = ""
    if (name != ""):
        nameQuery = f"name={name}"
    if (cv_id != ""):
        cvQuery = f"&cv={get_cv_name(cv_id, region)}"
    if class_name != "":
        clsNameQuery= f"&className={class_name}"
    response = session.get(
        f"https://api.atlasacademy.io/basic/{region}/servant/search?{nameQuery}{cvQuery}{clsNameQuery}")
    servants = json.loads(response.text)
    if not isinstance(servants, list) or len(servants) == 0:
        return []

    return servants


def get_servant_by_id(id: int, region: str = "JP"):
    """Get servant by ID

    Args:
        id (int): Servant ID
        region (str, optional): Region. Defaults to "JP".

    Returns:
        Servant object
    """
    response = session.get(
        f"https://api.atlasacademy.io/nice/{region}/servant/{id}?lore=true")
    servant = json.loads(response.text)
    if servant.get('detail') == "Svt not found":
        return None
    else:
        return servant


def create_servant_pages(servant, region):
    pages = []

    # Basic info
    embed = interactions.Embed(
        title="Basic Info",
        description="",
        color=interactions.Color.blurple()
    )
    faceAssetUrl = servant.get('extraAssets').get('faces').get('ascension').get('1')
    if faceAssetUrl == None:
        faceAssetUrl = servant.get('extraAssets').get('faces').get('ascension').get('0')
    embed.set_thumbnail(
        url=faceAssetUrl
    )

    servant_name = servant.get('name')
    if region == "JP" and servant.get('name') != servant.get('ruby'):
        servant_name += "\n" + servant.get('ruby')
    embed.add_field("Name", servant_name, True)
    embed.add_field("Rarity", "★"*servant.get('rarity'), True)
    embed.add_field("Class", title_case(servant.get('className')), True)
    embed.add_field("Attribute", title_case(servant.get('attribute')), True)
    embed.add_field("Cards", (
        f"{servant.get('cards')[0][0].upper()}"
        f"{servant.get('cards')[1][0].upper()}"
        f"{servant.get('cards')[2][0].upper()}"
        f"{servant.get('cards')[3][0].upper()}"
        f"{servant.get('cards')[4][0].upper()}"
    ), True)
    traits = servant.get("traits")
    alignments = []
    otherTraits = []
    for trait in traits:
        if (str(trait.get("id"))[0] == "3" and len(str(trait.get("id"))) == 3):
            alignments.append(title_case(
                trait.get("name").replace("alignment", "")))
        if (str(trait.get("id"))[0] == "2" and len(str(trait.get("id"))) == 4):
            otherTraits.append(title_case(trait.get("name")))

    if len(alignments) > 0:
        embed.add_field("Alignments", " ".join(alignments), True)

    if len(otherTraits) > 0:
        embed.add_field("Traits", ", ".join(otherTraits))

    embed.add_field("Gender", title_case(servant.get("gender")), True)
    embed.add_field("Voice Actor", servant.get("profile").get("cv"), True)
    embed.add_field("Illustrator", servant.get(
        "profile").get("illustrator"), True)

    pages.append(Page(f"Basic Info", embed))

    # Skills
    if len(servant.get('skills')) > 0:
        embed = interactions.Embed(
            title="Skills",
            description=f"{servant.get('name')} ({title_case(servant.get('className'))})",
            color=interactions.Color.blurple()
        )
        embed.set_thumbnail(
            url=faceAssetUrl
        )

        # Sort Skill No ASC, ID ASC (Unlocks after strengthening)
        for skill in sorted(servant.get('skills'), key=lambda s: (s.get('num'), s.get('id'))):
            embed.add_field(
                f"Skill {skill.get('num')}: {skill.get('name')}", skill.get('detail'))
        pages.append(Page(f"Skills", embed))
    
    # Skill materials
    embed = interactions.Embed(
        title="Skill Materials",
        description=f"{servant.get('name')} ({title_case(servant.get('className'))})",
        color=interactions.Color.blurple()
    )
    for id, skillMats in servant.get("skillMaterials").items():
        skillMaterialText = []
        for item in skillMats.get("items"):
            itemUrl = f"https://apps.atlasacademy.io/db/{region}/item/{item.get('item').get('id')}"
            skillMaterialText.append(f"[{item.get('item').get('name')}]({itemUrl}) x {item.get('amount')}")
        skillMaterialText.append(f"QP: {'{:,}'.format(skillMats.get('qp'))}")
        embed.add_field(f"{int(id) - 1}→{id}:", "\n".join(skillMaterialText), True)
    pages.append(Page(f"Skill Materials", embed))

    # NPs
    if len(servant.get("noblePhantasms")) > 0:
        embed = interactions.Embed(
            title="Noble Phantasms",
            description=f"{servant.get('name')} ({title_case(servant.get('className'))})",
            color=interactions.Color.blurple()
        )
        embed.set_thumbnail(
            url=faceAssetUrl
        )
        for i, noblePhantasm in enumerate(servant.get("noblePhantasms")):
            embed.add_field(
                f"Noble Phantasm {i + 1}: {noblePhantasm.get('name')} {noblePhantasm.get('rank')} ({noblePhantasm.get('card').capitalize()})",
                noblePhantasm.get('detail')
            )
        pages.append(Page(f"Noble Phantasms", embed))

    # Ascensions
    ascensions = servant.get("extraAssets").get("charaGraph").get("ascension")
    ascensionCount = 0
    for id, ascensionImgUrl in ascensions.items():
        embed = interactions.Embed(
            title=f"Ascension #{ascensionCount + 1}",
            description=f"{servant.get('name')} ({title_case(servant.get('className'))})",
            color=interactions.Color.blurple()
        )

        descText = []
        ascensionItems = servant.get("ascensionMaterials").get(str(ascensionCount)).get("items")
        for ascensionItem in ascensionItems:
            itemUrl = f"https://apps.atlasacademy.io/db/{region}/item/{ascensionItem.get('item').get('id')}"
            descText.append(f"[{ascensionItem.get('item').get('name')}]({itemUrl}) x {ascensionItem.get('amount')}")
        qpCount = servant.get("ascensionMaterials").get(str(ascensionCount)).get("qp")
        descText.append(f"QP: {'{:,}'.format(qpCount)}")
        embed.add_field("Required Materials", "\n".join(descText))
        embed.set_image(url=ascensionImgUrl)
        pages.append(Page(f"Ascension #{ascensionCount + 1}", embed))
        ascensionCount += 1

    return pages


def get_functions(type: str, target: str = "", region: str = "JP"):
    """Gets all the effects (functions) with the specified effect.

    Args:
        type (str): Effect name
        target (str): Effect target
        region (str): Region (Default: JP)

    Returns:
        A list of functions with the specified effect.
    """
    if type == "":
        return []
    targetQueryStr = ""
    if target != "":
        targetQueryStr = f"&targetType={target}"
    url = f"https://api.atlasacademy.io/basic/{region}/function/search?reverse=true&reverseDepth=servant&type={type}{targetQueryStr}"
    response = session.get(url)
    functions = json.loads(response.text)
    return functions


def get_functions_by_trait(trait: str, target: str = "", region: str = "JP"):
    """Gets all the effects (functions) with the specified trait effect.

    Args:
        trait (str): Trait ID
        target (str): Effect target
        region (str): Region (Default: JP)

    Returns:
        A list of functions with the specified effect.
    """
    if trait == "":
        return []
    targetQueryStr = ""
    if target != "":
        targetQueryStr = f"&targetType={target}"

    url = f"https://api.atlasacademy.io/basic/{region}/function/search?reverse=true&reverseDepth=servant&tvals={trait}{targetQueryStr}"
    response = session.get(url)
    functions = json.loads(response.text)
    return functions


def get_skills_from_functions(functions, flag: str = "skill"):
    found_skills = []
    for function in functions:
        for skill in function.get('reverse').get('basic').get(flag):
            if skill.get('name') == "" or skill.get('type') == "passive":
                continue
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


def get_skills_with_type(type: str, flag: str = "skill", target: str = "", region: str = "JP"):
    """Get a list of skills or NP with the selected effects.

    Args:
        type (str): Effect name,
        flag (str, optional): "skill" or "NP". Defaults to "skill".
        target (str): Effect target
        region (str): Region (Default: JP)

    Returns:
        A list of skill objects with the specified effect.
    """
    if type == "":
        return None
    functions = get_functions(type, target, region)
    found_skills = get_skills_from_functions(functions, flag)
    return found_skills


def get_skills_with_trait(trait: str, flag: str = "skill", target: str = "", region: str = "JP"):
    """Get a list of skills or NP that are effective against the specified trait.

    Args:
        trait (str): Trait ID
        flag (str, optional): "skill" or "NP". Defaults to "skill".
        target (str): Effect target
        region (str): Region (Default: JP)

    Returns:
        A list of skill objects with the specified effect.
    """
    if flag == "skill":
        functions = get_functions_by_trait(trait, target, region)
        found_skills = get_skills_from_functions(functions, flag)
        return found_skills
    elif flag == "NP":
        found_nps = get_nps_with_trait(trait, region)
        return found_nps
    return None


def get_nps_with_trait(trait: str, region: str = "JP"):
    url = f"https://api.atlasacademy.io/basic/{region}/NP/search?svalsContain={trait}&reverse=true"
    response = session.get(url)
    nps = json.loads(response.text)
    return nps


def get_skills_with_buff(buffType: str = "", flag: str = "skill", region: str = "JP"):
    if buffType == "":
        return None
    url = f"https://api.atlasacademy.io/basic/{region}/buff/search?reverse=true&reverseDepth=servant&reverseData=basic&type={buffType}"
    response = session.get(url)
    buffs = json.loads(response.text)
    skills = []
    for buff in buffs:
        functions = buff.get("reverse").get("basic").get("function")
        skills.extend(get_skills_from_functions(functions, flag))

    return skills


def get_skill_details(id: str = "", flag: str = "skill", region: str = "JP"):
    if id == "":
        return None
    url = f"https://api.atlasacademy.io/nice/{region}/{flag}/{id}"
    response = session.get(url)
    return json.loads(response.text)


def get_skills(
    type: str = "",
    type2: str = "",
    flag: str = "skill",
    target: str = "",
    buffType1: str = "",
    buffType2: str = "",
    trait: str = "",
    region: str = "JP"
):
    """Get skills or noble phantasms with the selected effects.

    Args:
        type (str): Effect 1
        type2 (str, optional): Effect 2
        flag (str, optional): "skill" for skills or "NP" for noble phantasm. Defaults to "skill".
        target (str): Effect target
        buffType1 (str): Buff effect 1
        buffType2 (str): Buff effect 2
        trait (str): Affected trait
        region (str): Region (Default: JP)

    Returns:
        Pages of embeds containing the skills data.
    """
    found_list_1 = get_skills_with_type(type, flag, target, region)
    found_list_2 = get_skills_with_type(type2, flag, target, region)
    found_buff_list1 = get_skills_with_buff(buffType1, flag, region)
    found_buff_list2 = get_skills_with_buff(buffType2, flag, region)
    found_trait_list = get_skills_with_trait(trait, flag, target, region)
    matched_skills_list = common_elements(
        found_list_1, found_list_2, found_buff_list1, found_buff_list2, found_trait_list
    )

    embeds = []
    embed = create_embed(type, type2, flag, target,
                         buffType1, buffType2, trait, region)
    maxLimit = 5
    pageCount = 0
    totalCount = 0
    for skill in matched_skills_list:
        skillDetails = get_skill_details(skill.get('id'), flag)
        if (skillDetails.get('type') == "passive"):
            continue
        servants = skill.get('reverse').get('basic').get('servant')
        servantList = []
        for servant in servants:
            if (
                servant.get('name') == "" or
                (servant.get('type') != "normal" and servant.get('type')
                 != "heroine")  # Mash has her own category lmao
            ):
                continue
            servant_id = f"{servant.get('name')} ({title_case(servant.get('className'))})"
            if servant_id not in servantList:
                totalCount += 1
                servantList.append(servant_id)
                if pageCount >= maxLimit:
                    embeds.append(embed)
                    embed = create_embed(
                        type, type2, flag, target, buffType1, buffType2, trait, region)
                    pageCount = 0
                skillName = skill.get('name')
                embed.add_field(
                    f"{totalCount}: {servant.get('name')} ({title_case(servant.get('className'))})\n",
                    (
                        f"[{skillName}](https://apps.atlasacademy.io/db/{region}/{'skill' if flag == 'skill' else 'noble-phantasm'}/{skill.get('id')})"
                    )
                )
                pageCount += 1

    if (totalCount == 0):
        embed.add_field("Not found.", "Try different parameters")
    embeds.append(embed)
    pages = []
    cnt = 0
    for resEmbed in embeds:
        cnt += 1
        pages.append(Page(
            f"{1 + maxLimit * (cnt - 1)}-{min(totalCount, cnt * maxLimit)} of {totalCount}" if totalCount > 0 else "", resEmbed))

    return pages


def create_embed(type: str = "", type2: str = "", flag: str = "skill", target: str = "", buffType1: str = "", buffType2: str = "", trait: str = "", region: str = "JP"):
    """Creates an embed object for the result data.

    Args:
        type (str): Effect 1
        type2 (str, optional): Effect 2
        flag (str, optional): "skill" for skills or "NP" for noble phantasm. Defaults to "skill".
        target (str): Effect target
        buffType1 (str): Buff effect 1 (only works if type is 'buff')
        buffType2 (str): Buff effect 2 (only works if type2 is 'buff')
        region (str): Region (Default: JP)

    Returns:
        `interactions.Embed`: Embed object
    """
    embed = interactions.Embed(
        title=f"{'Skills' if flag == 'skill' else 'Noble Phantasms'}",
        description="",
        color=interactions.Color.blurple()
    )

    if type != "":
        embed.add_field("Type 1", title_case(type), True)
    if type2 != "":
        embed.add_field("Type 2", title_case(type2), True)
    if target != "":
        embed.add_field("Target", title_case(target), True)
    if buffType1 != "":
        embed.add_field("Buff 1", title_case(buffType1), True)
    if buffType2 != "":
        embed.add_field("Buff 2", title_case(buffType2), True)
    if trait != "":
        embed.add_field("Affected Trait", title_case(get_traits()[trait]), True)
    if region != "":
        embed.add_field("Region", region, True)

    return embed


def common_elements(*lists):
    """Finds common elements in a list of lists
    """
    common_list = []
    for list in lists:
        if list == None:
            continue
        if len(list) == 0:
            return []
        if len(common_list) == 0 and len(list) > 0:
            common_list.extend(list)
            continue
        common_list = [element for element in common_list if element in list]
    res = []
    [res.append(x) for x in common_list if x not in res]
    return res


# Commands
@bot.command(
    description="Servant info lookup",
)
@interactions.option(str, name="servant-name", description="Servant name", required=False)
@interactions.option(str, name="cv", description="CV", required=False, autocomplete=True)
@interactions.option(str, name="class-name", description="Class name", required=False, autocomplete=True)
@interactions.option(str, name="region", description="Region (Default: JP)", required=False, autocomplete=True)
async def servant(
    ctx: interactions.CommandContext,
    servantName: str = "",
    cv: str = "",
    className: str = "",
    region: str = "JP"
):
    if servantName == "" and cv == "" and className == "":
        await ctx.send("Invalid input.")
        return

    await ctx.defer()
    servants = get_servant(servantName, cv, className, region)
    if servants == None or len(servants) == 0:
        await ctx.send("Not found.")
        return
    if len(servants) == 1:
        servant = get_servant_by_id(servants[0].get("id"), region)
        pages = create_servant_pages(servant, region)
        await send_paginator(ctx, pages)
    else:
        options = []
        for index, servant in enumerate(servants):
            options.append(interactions.SelectOption(
                label=f"{index + 1}: {servant.get('name')} ({title_case(servant.get('className'))})", value=f"{servant.get('id')}:{region}"))
        selectMenu = interactions.SelectMenu(
            options=options,
            placeholder="Select one...",
            custom_id="menu_component",
        )
        embed = interactions.Embed(
            title=f"{len(servants)} matches found.",
            color=interactions.Color.blurple()
        )

        if servantName != "":
            embed.add_field("Servant name", servantName, True)
        if cv != "":
            embed.add_field("CV", get_cv_name(cv, region), True)
        if className != "":
            embed.add_field("Class", title_case(className), True)
        if region != "":
            embed.add_field("Region", region, True)
        await ctx.send(content=None, components=selectMenu, embeds=embed)


@bot.component("menu_component")
async def select_response(ctx, value=[]):
    id = value[0].split(":")[0]
    region = value[0].split(":")[1]
    servant = get_servant_by_id(id, region)
    pages = create_servant_pages(servant, region)
    await send_paginator(ctx, pages)


@bot.command(
    description="Search for servants with skills that matches the specified parameters",
)
@interactions.option(str, name="type", description="Effect 1", required=False, autocomplete=True)
@interactions.option(str, name="type2", description="Effect 2", required=False, autocomplete=True)
@interactions.option(str, name="target", description="Target", required=False, autocomplete=True)
@interactions.option(str, name="buff", description="Buff 1", required=False, autocomplete=True)
@interactions.option(str, name="buff2", description="Buff 2", required=False, autocomplete=True)
@interactions.option(str, name="trait", description="Affected trait", required=False, autocomplete=True)
@interactions.option(str, name="region", description="Region (Default: JP)", required=False, autocomplete=True)
async def skill(
    ctx: interactions.CommandContext,
    type: str = "",
    type2: str = "",
    target: str = "",
    buff: str = "",
    buff2: str = "",
    trait: str = "",
    region: str = "JP",
):
    if (type == "" and type2 == "" and target == "" and buff == "" and buff2 == "" and trait == ""):
        await ctx.send("Invalid input.")
        return

    await ctx.defer()
    pages = get_skills(type, type2, "skill", target, buff, buff2, trait, region)
    await send_paginator(ctx, pages)


@bot.command(
    description="Search for servants with NP that matches the specified parameters",
)
@interactions.option(str, name="type", description="Effect 1", required=False, autocomplete=True)
@interactions.option(str, name="type2", description="Effect 2", required=False, autocomplete=True)
@interactions.option(str, name="target", description="Target", required=False, autocomplete=True)
@interactions.option(str, name="buff", description="Buff 1", required=False, autocomplete=True)
@interactions.option(str, name="buff2", description="Buff 2", required=False, autocomplete=True)
@interactions.option(str, name="trait", description="Affected trait", required=False, autocomplete=True)
@interactions.option(str, name="region", description="Region (Default: JP)", required=False, autocomplete=True)
async def np(
    ctx: interactions.CommandContext,
    type: str = "",
    type2: str = "",
    target: str = "",
    buff: str = "",
    buff2: str = "",
    trait: str = "",
    region: str = "JP",
):
    if (type == "" and type2 == "" and target == "" and buff == "" and buff2 == "" and trait == ""):
        await ctx.send("Invalid input.")
        return

    await ctx.defer()
    pages = get_skills(type, type2, "NP", target, buff, buff2, trait, region)
    await send_paginator(ctx, pages)


@bot.command(
    description="Search for servants with NP and/or skills that matches the specified parameters",
    name="skill-or-np"
)
@interactions.option(str, name="type", description="Effect 1", required=False, autocomplete=True)
@interactions.option(str, name="type2", description="Effect 2", required=False, autocomplete=True)
@interactions.option(str, name="target", description="Target", required=False, autocomplete=True)
@interactions.option(str, name="buff", description="Buff 1", required=False, autocomplete=True)
@interactions.option(str, name="buff2", description="Buff 2", required=False, autocomplete=True)
@interactions.option(str, name="trait", description="Affected trait", required=False, autocomplete=True)
@interactions.option(str, name="region", description="Region (Default: JP)", required=False, autocomplete=True)
async def skillOrNp(
    ctx: interactions.CommandContext,
    type: str = "",
    type2: str = "",
    target: str = "",
    buff: str = "",
    buff2: str = "",
    trait: str = "",
    region: str = "JP",
):
    if (type == "" and type2 == "" and target == "" and buff == "" and buff2 == "" and trait == ""):
        await ctx.send("Invalid input.")
        return

    await ctx.defer()
    pages = get_skills(type, type2, "skill", target, buff, buff2, trait, region)
    pages.extend(get_skills(type, type2, "NP", target, buff, buff2, trait, region))
    await send_paginator(ctx, pages)


async def send_paginator(ctx: interactions.CommandContext, pages):
    """ Creates a paginator for the pages

    Args:
        ctx (interactions.CommandContext): Application context
        pages (_type_): Result data
    """
    if pages == None or len(pages) == 0:
        await ctx.send("No result.")
    if len(pages) == 1:
        await ctx.send(embeds=pages[0].embeds)
    elif len(pages) >= 2:
        await Paginator(
            client=bot,
            ctx=ctx,
            pages=pages,
        ).run()


# Autocomplete functions
def get_enums(enum_type: str):
    response = session.get(
        f"https://api.atlasacademy.io/export/JP/nice_enums.json")  # JP and NA use the same enums
    enums = json.loads(response.text)
    return enums.get(enum_type)


def get_traits():
    response = session.get(
        f"https://api.atlasacademy.io/export/JP/nice_trait.json")  # JP and NA use the same enums
    return json.loads(response.text)


def title_case(string):
    if (string == ""):
        return
    words = re.sub('([A-Z][a-z]+)', r' \1', re.sub('([A-Z]+)', r' \1', string)).split()
    if len(words) > 0:
        words[0] = words[0][0].upper() + words[0][1:]
    return " ".join(words)


def populate_enum_list(enumName: str, input_value: str):
    fnEnums = get_enums(enumName)
    options = fnEnums.values()
    filteredOptions = [
        option for option in options
        if (input_value.upper() in option.upper() or input_value.upper() in title_case(option).upper())
    ]
    choices = []
    for option in filteredOptions[0:24]:
        text = title_case(option)
        choices.append(interactions.Choice(name=text, value=option))
    return choices


def populate_traits(input_value: str):
    traits = get_traits()
    # Traits ID which starts with 2 and has 4 digits
    filteredTraits = dict(filter(lambda elem:
        str(elem[0])[0] == "2" and
        len(str(elem[0])) == 4 and
        (input_value.upper() in elem[1].upper() or input_value.upper() in title_case(elem[1]).upper()),
        traits.items()
        )
    )
    choices = []
    for trait in list(filteredTraits.items())[:24]:
        text = title_case(trait[1])
        choices.append(interactions.Choice(name=text, value=trait[0]))
    return choices

# Load CV list
session = requests_cache.CachedSession()
response = session.get(
    f"https://api.atlasacademy.io/export/JP/nice_cv.json")
cv_list_jp = json.loads(response.text)
response = session.get(
    f"https://api.atlasacademy.io/export/JP/nice_cv_lang_en.json")
cv_list_jp_en = json.loads(response.text)
cv_list = {}
for cv_jp in cv_list_jp:
    cv_en = next(cv for cv in cv_list_jp_en if cv.get("id") == cv_jp.get("id"))
    cv_list[cv_jp.get("id")] = f"{cv_jp.get('name')} ({cv_en.get('name')})"


def populate_cv(input_value: str):
    matched_cvs = [
        cv for cv in cv_list.items() if input_value.upper() in cv[1].upper()
    ]
    choices = []
    for cv in matched_cvs[0:24]:
        choices.append(interactions.Choice(name=cv[1], value=str(cv[0])))
    return choices


def get_cv_name(cv_id: str, region: str = "JP"):
    if region == "JP":
        cv_name = next(cv for cv in cv_list_jp if cv.get("id") == int(cv_id))
    elif region == "NA":
        cv_name = next(
            cv for cv in cv_list_jp_en if cv.get("id") == int(cv_id))
    return cv_name.get('name')


@bot.autocomplete(command="servant", name="cv")
async def autocomplete_choice_list(ctx: interactions.CommandContext, cv: str = ""):
    await ctx.populate(populate_cv(cv))


@bot.autocomplete(command="servant", name="class-name")
async def autocomplete_choice_list(ctx: interactions.CommandContext, className: str = ""):
    await ctx.populate(populate_enum_list("SvtClass", className))


@bot.autocomplete(command="skill", name="type")
@bot.autocomplete(command="np", name="type")
@bot.autocomplete(command="skill-or-np", name="type")
async def autocomplete_choice_list(ctx: interactions.CommandContext, type: str = ""):
    await ctx.populate(populate_enum_list("NiceFuncType", type))


@bot.autocomplete(command="skill", name="type2")
@bot.autocomplete(command="np", name="type2")
@bot.autocomplete(command="skill-or-np", name="type2")
async def autocomplete_choice_list(ctx: interactions.CommandContext, type2: str = ""):
    await ctx.populate(populate_enum_list("NiceFuncType", type2))


@bot.autocomplete(command="skill", name="target")
@bot.autocomplete(command="np", name="target")
@bot.autocomplete(command="skill-or-np", name="target")
async def autocomplete_choice_list(ctx: interactions.CommandContext, target: str = ""):
    await ctx.populate(populate_enum_list("NiceFuncTargetType", target))


@bot.autocomplete(command="skill", name="buff")
@bot.autocomplete(command="np", name="buff")
@bot.autocomplete(command="skill-or-np", name="buff")
async def autocomplete_choice_list(ctx: interactions.CommandContext, buff: str = ""):
    await ctx.populate(populate_enum_list("NiceBuffType", buff))


@bot.autocomplete(command="skill", name="buff2")
@bot.autocomplete(command="np", name="buff2")
@bot.autocomplete(command="skill-or-np", name="buff2")
async def autocomplete_choice_list(ctx: interactions.CommandContext, buff2: str = ""):
    await ctx.populate(populate_enum_list("NiceBuffType", buff2))


@bot.autocomplete(command="servant", name="region")
@bot.autocomplete(command="skill", name="region")
@bot.autocomplete(command="np", name="region")
@bot.autocomplete(command="skill-or-np", name="region")
async def autocomplete_choice_list(ctx: interactions.CommandContext, region: str = ""):
    choices = []
    choices.append(interactions.Choice(name="NA", value="NA"))
    choices.append(interactions.Choice(name="JP", value="JP"))
    await ctx.populate(choices)


@bot.autocomplete(command="skill", name="trait")
@bot.autocomplete(command="np", name="trait")
@bot.autocomplete(command="skill-or-np", name="trait")
async def autocomplete_choice_list(ctx: interactions.CommandContext, trait: str = ""):
    await ctx.populate(populate_traits(trait))

bot.start()
