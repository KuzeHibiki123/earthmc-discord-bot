import os
import discord
import requests
import json
import aiohttp
import asyncio
import matplotlib
import math
import time
import io
import datetime
import numpy as np
import pandas as pd
matplotlib.use("Agg") 
import matplotlib.pyplot as plt
from matplotlib import font_manager
from discord.ext import commands
from requests import Response
from discord.ext import tasks
token=""
intents= discord.Intents.default()
intents.message_content=True
bot=commands.Bot(command_prefix="!",intents=intents)
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC"]
plt.rcParams["axes.unicode_minus"] = False
API = "https://api.earthmc.net/v4"
with open("language.json","r",encoding="utf-8") as f:
    userlang=json.load(f)
with open("zh_cn.json","r",encoding="utf-8") as f:
    zh=json.load(f)
with open("en_us.json","r",encoding="utf-8") as f:
    en=json.load(f)
#函数部分
_cache = {}
async def fetch_mctiers(uuid):
    url = f"https://mctiers.com/api/v2/profile/{uuid}/rankings"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                text = await r.text()
                if r.status != 200:
                    return None
                return await r.json()
    except Exception as e:
        return None
def TF(ctx,values):
    if values==True:
        return lang(ctx,"True")
    else:
        return lang(ctx,"False")
def make_autopct(values):
    def my_autopct(pct):
        total = sum(values)
        val = pct * total / 100
        return f"{pct:.1f}%\n{val:,.0f}G"
    return my_autopct
@bot.command()
async def api_post(session, path, payload):
    async with session.post(f"{API}/{path}", json=payload) as r:
        r.raise_for_status()
        return await r.json()
async def api_post_batched(session, path, key, items, size=20):
    out = []
    for i in range(0, len(items), size):
        chunk = items[i:i + size]
        out.extend(await api_post(session, path, {key: chunk}))
    return out
async def get_nation(session, name):
    data = await api_post(session, "nations", {"query": name})
    return data[0] if data else None
async def get_town(session, query):
    data = await api_post(session, "towns", {"query": query})
    return data[0] if data else None
#语言
def userlanread(ctx):
    try:
        with open("language.json", "r", encoding="utf-8") as f:
            all_lang = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return "zh"
    return all_lang.get(str(ctx.author.id), "zh")
def lang(ctx,key,**kwargs):
    user_lang=userlanread(ctx)
    texts = zh if user_lang == "zh" else en
    s = texts.get(key, key)
    return s.format(**kwargs) if kwargs else s
#饼图
async def get_players(session, uuids):
    if not uuids:
        return []
    return await api_post_batched(session, "players", "query", uuids, size=20)
async def get_player(session, uuid):
    data = await api_post(session, "players", {"query": uuid})
    return data[0] if data else None
def pie_chart(labels, values, title):
    fig, ax = plt.subplots(figsize=(8, 8))
    pairs = sorted(zip(labels, values), key=lambda x: -x[1])
    total = sum(values) or 1
    main, other = [], 0
    for name, v in pairs:
        if v / total < 0.02:       
            other += v
        else:
            main.append((name, v))
    if other:
        main.append(("其他", other))

    lbl = [n for n, _ in main]
    val = [v for _, v in main]

    ax.pie(val, labels=lbl,  autopct=make_autopct(val), startangle=90,
           counterclock=False)
    ax.set_title(title)
    ax.axis("equal")

    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", dpi=110)
    plt.close(fig)
    buf.seek(0)
    return buf
#vpremind
async def vpreminding(ctx):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.earthmc.net/v4/voteparty") as r:
                if r.status != 200:
                    return
                data = await r.json()
    except Exception:
        return  

    vp = data.get("voteParty") or data.get("voteparty") or {}
    vp_num = vp.get("numRemaining")
    if vp_num is None:
        return
    vp_num = int(vp_num)
    try:
        with open("reminder.json", "r", encoding="utf-8") as f:
            remindingdata = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return
    mentions = []
    for uid, threshold in remindingdata.items():
        try:
            threshold = int(threshold)
        except (TypeError, ValueError):
            continue
        if vp_num <= threshold:
            mentions.append(f"<@{uid}>")
    if not mentions:
        return
    await channel.send(" ".join(mentions))
@tasks.loop(minutes=15)
async def vp_watcher():
    channel = bot.get_channel(1530281289280917534)
    if channel:
        await vpreminding(channel)
@bot.event
async def on_ready():
    if not vp_watcher.is_running():
        vp_watcher.start()
#饼图输出
async def collect_nation_wealth(nation_name):
    async with aiohttp.ClientSession() as session:
        nation = await get_nation(session, nation_name)
        if not nation:
            return None

        capital = (nation.get("capital") or {}).get("name")
        nation_balance = (nation.get("stats") or {}).get("balance", 0) or 0

        raw_towns = nation.get("towns") or []
        town_uuids = [
            t if isinstance(t, str) else t.get("uuid")
            for t in raw_towns
        ]
        town_uuids = [u for u in town_uuids if u]

        towns_data = await api_post_batched(
            session, "towns", "query", town_uuids, size=20
        ) if town_uuids else []

        town_residents = {}
        town_balance = {}
        all_resident_uuids = set()

        for t in towns_data:
            tname = t.get("name") or t.get("uuid")
            residents = t.get("residents") or []
            ruuids = [
                r if isinstance(r, str) else r.get("uuid")
                for r in residents
            ]
            ruuids = [u for u in ruuids if u]
            tstats = t.get("stats") or {}
            tbalance = tstats.get("balance") or 0
            town_residents[tname] = ruuids
            all_resident_uuids.update(ruuids)
            town_balance[tname] = tbalance
            if tname == capital:
                town_balance[tname] += nation_balance

        if not all_resident_uuids:
            return {
                "nation": nation,
                "town_wealth": {},
                "resident_wealth": {},
                "towns_data": towns_data,
                "error": "no_residents",
            }

        all_resident_uuids = list(all_resident_uuids)
        players = await get_players(session, all_resident_uuids)

    p_info = {}
    for p in players:
        uuid = p.get("uuid")
        name = p.get("name") or uuid
        stats = p.get("stats") or {}
        bal = stats.get("balance", 0) or 0
        try:
            bal = float(bal)
        except (TypeError, ValueError):
            bal = 0
        p_info[uuid] = (name, bal)

    town_wealth = {}
    resident_wealth = {}
    for tname, ruuids in town_residents.items():
        s = 0
        for u in ruuids:
            if u in p_info:
                nm, bal = p_info[u]
                s += bal
                resident_wealth[nm] = bal
        town_wealth[tname] = s + town_balance.get(tname, 0)

    missing_total = sum(
        1
        for ruuids in town_residents.values()
        for u in ruuids
        if u not in p_info
    )
    missing_by_town = {
        tname: [u for u in ruuids if u not in p_info]
        for tname, ruuids in town_residents.items()
    }
    missing_by_town = {k: v for k, v in missing_by_town.items() if v}

    town_wealth = {k: v for k, v in town_wealth.items() if v > 0}
    resident_wealth = {k: v for k, v in resident_wealth.items() if v > 0}

    return {
        "nation": nation,
        "capital": capital,
        "town_wealth": town_wealth,
        "resident_wealth": resident_wealth,
        "towns_data": towns_data,
        "missing_total": missing_total,
        "missing_by_town": missing_by_town,
    }
#土地
async def collect_nation_plots(nation_name):
    async with aiohttp.ClientSession() as session:
        nation = await get_nation(session, nation_name)
        if not nation:
            return None

        raw_towns = nation.get("towns") or []
        town_uuids = [
            t if isinstance(t, str) else t.get("uuid")
            for t in raw_towns
        ]
        town_uuids = [u for u in town_uuids if u]

        towns_data = await api_post_batched(
            session, "towns", "query", town_uuids, size=20
        ) if town_uuids else []

    town_plots = {}
    for t in towns_data:
        tname = t.get("name") or t.get("uuid")
        tstats = t.get("stats") or {}
        tplot = tstats.get("numTownBlocks") or 0
        town_plots[tname] = tplot

    total_plots = sum(town_plots.values())
    total_value = total_plots * 16

    town_plots = {k: v for k, v in town_plots.items() if v > 0}

    return {
        "nation": nation,
        "town_plots": town_plots,
        "total_plots": total_plots,
        "total_value": total_value,
    }
#gdp 汇总
@bot.hybrid_command(name="gdp")
async def gdp(ctx, nation_name: str):
    await ctx.defer()

    result = await collect_nation_wealth(nation_name)
    plot_result=await collect_nation_plots(nation_name)
    if result is None or plot_result is None:
        await ctx.send("找不到该国家")
        return
    if result.get("error") == "no_residents":
        await ctx.send("该国没有居民")
        return

    town_wealth = result["town_wealth"]
    resident_wealth = result["resident_wealth"]
    total_plots=plot_result["total_plots"]
    total_value=plot_result["total_value"]
    sumgdp=sum(town_wealth.values())+total_value
    if not town_wealth and not resident_wealth:
        await ctx.send("没有可统计的财产数据")
        return

    loop = asyncio.get_running_loop()

    buf1 = await loop.run_in_executor(
        None, pie_chart,
        list(town_wealth.keys()), list(town_wealth.values()),
        f"{nation_name} 各城镇财产占比"
    )
    top = sorted(resident_wealth.items(), key=lambda x: -x[1])[:15]
    buf2 = await loop.run_in_executor(
        None, pie_chart,
        [n for n, _ in top], [v for _, v in top],
        f"{nation_name} 财产最多的居民占比 (Top15)"
    )

    top_towns = sorted(town_wealth.items(), key=lambda x: -x[1])[:5]
    top_residents = sorted(resident_wealth.items(), key=lambda x: -x[1])[:5]

    town_lines = "\n".join(
        f"{i}. **{n}** — {v:,.2f}G"
        for i, (n, v) in enumerate(top_towns, 1)
    )
    resident_lines = "\n".join(
        f"{i}. **{n}** — {v:,.2f}G"
        for i, (n, v) in enumerate(top_residents, 1)
    )

    embed = discord.Embed(
        title=f"{nation_name} 财产统计",
        color=0x57F287,
        description=(
                f"GDP总值: **{sumgdp}**\n"
                f"区块总和 **{total_plots}**\n"
                f"区块总价值 **{total_value}**\n"
    )
    )
    embed.add_field(
        name="Top 5 城镇",
        value=town_lines or "无",
        inline=True,
    )
    embed.add_field(
        name="Top 5 居民",
        value=resident_lines or "无",
        inline=True,
    )
    buf1.seek(0)
    f1 = discord.File(buf1, filename="towns.png")
    embed.set_image(url="attachment://towns.png")
    await ctx.send(embed=embed, files=[f1])
#同步指令
@bot.command()
async def synccommands(ctx):
    await bot.tree.sync()
    await ctx.send("已同步")
#功能部分
@bot.hybrid_command(name="town",description="查询城镇资料")
async def town(ctx,town_name:str):
    resp = requests.post('https://api.earthmc.net/v4/towns', json={"query": town_name})
    data = resp.json()
    if not data:
        await ctx.send("找不到该城镇")
        return
    town_data = data[0]       
    nation=town_data.get("nation")
    nation_name = nation.get("name") if nation else "无"
    mayor=town_data.get("mayor")
    mayor_name=mayor.get("name")
    await ctx.send(f"城镇名: {town_data['name']} 所属国家: {nation_name} 城主{mayor_name}")
@bot.hybrid_command(name="nation",description="查询国家资料")
async def nation(ctx,a:str):
    resp = requests.post('https://api.earthmc.net/v4/nations', json={"query": a})
    data = resp.json()
    if not data:
        await ctx.send("找不到该国家")
        return
    nation_data = data[0]
    capital=nation_data.get("capital")
    capital_name=capital.get("name")
    king=nation_data.get("king")
    king_name=king.get("name")           
    await ctx.send(f"国家: {nation_data['name']} 首都: {capital_name} 领导人{king_name}")
@bot.hybrid_command(name="vp",description="查询vp剩余票数")
async def vp(ctx):
    resp=requests.get('https://api.earthmc.net/v4/')
    data=resp.json()
    vp=data.get("voteParty")
    vp_num=vp.get("numRemaining")
    await ctx.send(f"距离vp还有{vp_num}票")
@bot.hybrid_command(name="language",description="更改语言")
async def language(ctx,lang_code:str):
    user=ctx.author
    if os.path.exists("reminder.json"):
        with open("language.json", "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = {}
    else:
        data = {}
    data[str(ctx.author.id)] = lang_code
    with open("language.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    await ctx.send(f"{lang(ctx, 'language_set')} {ctx.author.display_name}:{lang_code}")
@bot.hybrid_command()
async def version(ctx):
    await ctx.send(lang(ctx,'version'))
@bot.hybrid_command(name="ruin")
async def ruin(ctx,town:str):
    resp=requests.post('api.earthmc.net/v4/towns', json={"query": town})
    data=resp.json()
    town_data=data[0]
    time_stamp=town_data.get("timestamps")
    ruined_time_stmap=time_stamp.get("ruinedAt")
    await ctx.send(f"{lang(ctx,'ruinedtime')}{ruined_time_stmap}")
    mayor=town_data.get("mayor")
    mayor_name=mayor.get("name")
    resp1=requests.post('https://api.earthmc.net/v4/players', json={"query": mayor_name})
    data1=resp1.json()
    mayor_data = data1[0]
    timestamps = mayor_data.get("timestamps") or {}
    mayor_lli = timestamps.get("lastOnline")

    if mayor_lli is None:
        await ctx.send(lang(ctx,'player_not_found_ruin'))
        return

    dt = datetime.datetime.fromtimestamp(mayor_lli / 1000, tz=datetime.timezone.utc)
    now = datetime.datetime.now(datetime.timezone.utc)
    delta = now - dt
    days = delta.days
    hours = delta.seconds // 3600

    if days > 0:
        text = f"{41-days} day(s) {24-hours} hr(s)"
    else:
        text = f"41 days {hours} hr(s)"

    await ctx.send(f"{lang(ctx, 'mayortransfer')} {text}")
@bot.hybrid_command()
async def about(ctx):
     await ctx.send(lang(ctx, "about"))
@bot.hybrid_command(name="res")
async def res(ctx,player:str):
    resp = requests.post('https://api.earthmc.net/v4/players', json={"query": player})
    data = resp.json()
    if not data:
        await ctx.send(lang(ctx,"Invalidinput"))
        return
    emcdata=data[0] 
    player_name=emcdata.get("name")
    uuid=emcdata.get("uuid")
    pvp_lines = []
    pvp_json = await fetch_mctiers(uuid)

    if not pvp_json:
        pvp_lines.append(f"**{lang(ctx, 'no_tier')}**")
    else:
        if isinstance(pvp_json, list):
            pvp_json = pvp_json[0] if pvp_json else {}

        rankings = pvp_json if pvp_json else {}

        mode_order = [
            "overall", "vanilla", "sword", "axe", "smp",
            "uhc", "pot", "nethop", "crystal",
        ]

        for mode in mode_order:
            m = rankings.get(mode)
            if not m or m.get("tier") is None:
                continue
            tier = m["tier"]
            pos = m.get("pos", 0)
            peak = m.get("peak_tier")
            retired = m.get("retired")
            if pos == 0:
                prefix = "High"
            elif pos == 1:
                prefix = "Low"
            line = f"**{mode.capitalize()}:** {prefix} Tier {tier}"
            if peak and peak != tier:
                line += f" · Peak {peak}"
            if retired:
                line += " · retired"
            pvp_lines.append(line)

        if not pvp_lines:
            pvp_lines.append(f"**{lang(ctx, 'no_tier')}**")

    pvp_text = "\n".join(pvp_lines)
    nation=emcdata.get("nation")
    town=emcdata.get("town")
    nation_name=nation.get("name")
    town_name=town.get("name")
    status=emcdata.get("status")
    isOnline=status.get("isOnline")
    isKing=status.get("isKing")
    isMayor=status.get("isMayor")
    embed=discord.Embed(
        title=lang(ctx,"res_title"),
        description=(
        f"**{lang(ctx,"res_bi_title")}**\n"
        f"{lang(ctx,"res_player_name")} **{player_name}**\n"
        f"{lang(ctx,"res_uuid")} **{uuid}**\n"
        f"{lang(ctx,"res_nation")} **{nation_name}**\n"
        f"{lang(ctx,"res_town")} **{town_name}**\n"
        f"{lang(ctx,"isOnline")} **{TF(ctx,isOnline)}**\n"
        f"{lang(ctx,"isKing")} **{TF(ctx,isKing)}**\n"
        f"{lang(ctx,"isMayor")} **{TF(ctx,isMayor)}**\n"
        f"**{lang(ctx,"res_pvp_title")}**\n"
        f"{pvp_text}"
    ),
    ) 
    embed.set_thumbnail(url=f"https://minotar.net/avatar/{player_name}/256")
    await ctx.send(embed=embed)
bot.run(token)