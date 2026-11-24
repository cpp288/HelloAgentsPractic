"""
=============================================================================
 三国狼人杀 · AgentScope 2.x 练习版
=============================================================================

 教材出处：第六章 6.3.2 节「三国狼人杀游戏」
 运行条件：
   1. Python >= 3.11
   2. pip install agentscope  (本文件针对 2.0.x 编写)
   3. 配置 .env：LLM_API_KEY / LLM_BASE_URL / LLM_MODEL

 ────────────────────────────────────────────────────────────────────────────
 ⚠️ 重要说明：教材基于 AgentScope 1.x 写的，而 2025 年底 AgentScope 发了
              2.0 的大版本重构，整个 API 体系大变样：

   | 1.x（教材里的旧 API）      | 2.x（本文件实际 import 的）    |
   |----------------------------|-------------------------------|
   | agentscope.agents.DialogAgent | agentscope.agent.Agent（单数）|
   | agentscope.models.*        | agentscope.model.* （单数）    |
   | agentscope.messagehub.MsgHub | ❌ 已移除 → 本文件用共享列表模拟 |
   | agentscope.pipeline.FanoutPipeline | ❌ 已移除 → 用 asyncio.gather 并发 |
   | agent(msg, structured_model=X) | agent.reply(msg, structured_schema=X) |
   | msg.parsed                 | msg.structured_output         |
   | Agent.__init__(sys_prompt=) | Agent.__init__(system_prompt=) |

   所以本文件在"保持教材案例骨架不变"的前提下，做了两处"降级"：
     ① MsgHub 临时频道 → 用 GameController 里一个 List[Msg] 当共享频道，
       每次讨论完把全员发言追加进去，相当于模拟 MsgHub 自动广播的效果
     ② FanoutPipeline → 用 asyncio.gather + 手动循环，自己并发调 Agent

   核心思路（消息驱动 / 结构化输出 / 双重身份角色建模 / 容错）完全不变，
   只是底层 API 名换了。

 ────────────────────────────────────────────────────────────────────────────

 建议阅读顺序：
   ① 看 main() → ② 数据模型 → ③ 三国角色提示词
   ④ 看 PlayerAgent / ModeratorAgent（2.x 的 Agent 构造）
   ⑤ 看 GameController 的四个阶段
   ⑥ 回头对照上面的 1.x → 2.x 映射表

=============================================================================
"""

from __future__ import annotations

import asyncio                      # Python 原生异步：AgentScope 的一切都是 async
import os
import random
from enum import Enum
from typing import List, Optional, Dict

from dotenv import load_dotenv
from pydantic import BaseModel, Field  # 结构化输出的模型定义工具

# ------------------------------------------------------------
# 加载 .env（和 Chapter-04 里的 llm_client.py 保持一致）
# ------------------------------------------------------------
load_dotenv()
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL")
LLM_MODEL = os.getenv("LLM_MODEL_ID") or os.getenv("LLM_MODEL")  # 兼容两种命名

# ------------------------------------------------------------
# AgentScope 2.x 核心导入（全部单数，和 1.x 不同）
# ------------------------------------------------------------
from agentscope.message import Msg, TextBlock  # 2.x Msg.content 必须是 list[ContentBlock]，TextBlock 是最常用的"文本块"类型
from agentscope.agent import Agent                # 2.x 里的通用 Agent（取代 DialogAgent）
from agentscope.model import DeepSeekChatModel    # DeepSeek 模型封装（和你的 .env 配置对应）
from agentscope.credential import DeepSeekCredential  # 2.x 统一用 Credential 传递 API Key
from agentscope.event._event import TextBlockDeltaEvent  # reply_stream 里的"自然语言增量"事件类型


# 小工具：AgentScope 2.x 的 Msg.content 必须是 list[TextBlock]，
# 用这个 helper 一行搞定，省得每个地方都写 [TextBlock(text=xxx)]
def _m(name: str, text: str, role: str = "assistant") -> Msg:
    """快速构造一条只有纯文本内容的 Msg"""
    return Msg(name=name, content=[TextBlock(text=text)], role=role)


async def smart_reply(agent, msg, structured_schema=None):
    """
    同时拿到 Agent 的两样东西：
      1. natural_text: 模型真正说的自然语言（用于打印聊天 / 拼聊天历史）
      2. final_msg: 最终 Msg 对象，包含 structured_output dict（用于逻辑处理）
         —— 同时把 final_msg.content 里的占位文本替换成真实自然语言，
            这样把 final_msg 追加到聊天历史时也能拿到对的内容。

    为什么 smart：
      AgentScope 2.x 在 structured_schema 模式下不 yield TextBlockDeltaEvent，
      模型的自然语言思考被塞进了 structured_output 的某个字符串字段里
      （通常是 schema 里描述最宽泛的那个 str 字段，比如 DiscussionModel 的
      key_evidence）。我们从 dict 里挑最长的 str 值，就是模型真正想说的话。

      如果 structured_schema 本身没有合适的 str 字段（比如 VoteModel 只有
      target_name），就返回 "(无自然语言输出)"——这种决策环节本来也不需要
      打印长文本。
    """
    natural_text = ""
    final_msg: Optional[Msg] = None

    async for event_or_msg in agent.reply_stream(
        msg, structured_schema=structured_schema, yield_final_msg=True,
    ):
        if isinstance(event_or_msg, Msg):
            final_msg = event_or_msg

    if final_msg is None:
        raise RuntimeError("Agent 没有返回 final_msg")

    # 从 structured_output dict 里挖"自然语言"：挑最长的字符串值
    if final_msg.structured_output:
        candidates = [
            str(v) for v in final_msg.structured_output.values()
            if isinstance(v, str) and v.strip()
        ]
        if candidates:
            natural_text = max(candidates, key=len).strip()

    # 兜底：如果没有从 structured_output 里挖到，试试从 content 里取
    # （非 structured_schema 模式下 content 就是真实自然语言）
    if not natural_text and final_msg.content:
        for block in final_msg.content:
            text = getattr(block, "text", None)
            if text and text.strip() and text != "The required structured output is generated.":
                natural_text = text.strip()
                break

    natural_text = natural_text or "(无自然语言输出)"

    # 关键补丁：把 final_msg.content 里的占位文本替换成真实自然语言
    if final_msg.content and natural_text != "(无自然语言输出)":
        final_msg.content = [TextBlock(text=natural_text)]

    return natural_text, final_msg


# ======================================================================
# 0. 配置与常量
# ======================================================================

class GameRole(str, Enum):
    """游戏里的功能角色（狼人杀身份）"""
    WEREWOLF = "狼人"
    SEER     = "预言家"
    WITCH    = "女巫"
    VILLAGER = "村民"


# 三国人物 → 狼人杀身份 的映射（6 人局：2 狼 + 1 预言家 + 1 女巫 + 2 村民）
CHARACTER_ASSIGNMENT: Dict[str, GameRole] = {
    "孙权":   GameRole.WEREWOLF,
    "周瑜":   GameRole.WEREWOLF,
    "曹操":   GameRole.SEER,
    "张飞":   GameRole.WITCH,
    "司马懿": GameRole.VILLAGER,
    "赵云":   GameRole.VILLAGER,
}

MAX_ROUND = 5             # 最多跑几轮（防止跑一整夜）
MAX_DISCUSSION_ROUND = 3  # 每次讨论最多说几轮


# ======================================================================
# 1. 结构化输出模型（教材 6.3.2 (3) 的重点）
#    用 pydantic 把"游戏规则"直接写进数据模型，模型输出不合法就报错
# ======================================================================

class DiscussionModel(BaseModel):
    """讨论阶段输出：每个玩家表达观点时必须给出这三个字段"""
    reach_agreement: bool = Field(
        description="是否已经就今晚要击杀的目标达成一致",
        default=False,
    )
    confidence_level: int = Field(
        description="对当前推理的信心程度（1-10）",
        ge=1, le=10, default=5,
    )
    key_evidence: Optional[str] = Field(
        description="支撑你观点的关键证据（可以为空）",
        default=None,
    )


class WerewolfKillModel(BaseModel):
    """狼人投票：必须选一个目标"""
    target_name: str = Field(description="今晚要击杀的玩家姓名")


class SeerCheckModel(BaseModel):
    """预言家查验：只能查一名玩家"""
    target_name: str = Field(description="要查验的玩家姓名")


class WitchActionModel(BaseModel):
    """女巫行动：可以同时决定解药和毒药的使用"""
    use_antidote: bool = Field(description="是否使用解药救今晚被击杀的人")
    use_poison:   bool = Field(description="是否使用毒药毒杀一人")
    poison_target: Optional[str] = Field(
        description="毒药目标（如果不使用毒药则为 null）",
        default=None,
    )


class VoteModel(BaseModel):
    """白天投票：必须选一个要淘汰的玩家"""
    target_name: str = Field(description="要投票淘汰的玩家姓名")


# from __future__ import annotations 会让类型注解延迟求值，
# Pydantic 2.x 在这种情况下需要显式 rebuild 才能正确识别 Optional 等类型
for _model in (DiscussionModel, WerewolfKillModel, SeerCheckModel, WitchActionModel, VoteModel):
    _model.model_rebuild(force=True)


# ======================================================================
# 2. 角色提示词（教材 6.3.2 (4) 的重点：双重身份注入）
#    每个 Agent 既要知道自己是"狼人"还是"预言家"，
#    又要知道自己对应的三国人物性格
# ======================================================================

# 三国人物的性格摘要：给 LLM 一个"人设"，让说话风格不一样
CHARACTER_PERSONALITY: Dict[str, str] = {
    "孙权":   "年轻气盛、善用权谋、表面谦厚但内里果决",
    "周瑜":   "智谋过人、自信骄傲、以大局为重",
    "曹操":   "多疑、精明、知人善任、宁我负人毋人负我",
    "张飞":   "直来直去、重义气、说话直白、易冲动",
    "司马懿": "隐忍谨慎、善于观察、长期布局",
    "赵云":   "忠心耿耿、勇武果敢、为人正直",
}


def build_system_prompt(name: str, role: GameRole) -> str:
    """为每个 Agent 生成 System Prompt：三国人格 + 狼人杀身份 + 游戏规则 + 输出格式"""
    personality = CHARACTER_PERSONALITY[name]

    role_tip = {
        GameRole.WEREWOLF: (
            "你是狼人阵营，目标是消灭所有好人。"
            "夜晚与其他狼人秘密协商击杀目标；白天隐藏身份、误导好人。"
        ),
        GameRole.SEER: (
            "你是预言家，好人阵营的领袖。"
            "每晚可查验一名玩家的身份（好人/狼人），但不能直接告诉别人。"
        ),
        GameRole.WITCH: (
            "你是女巫，好人阵营的治疗者。"
            "有一瓶解药（可救一次被杀的人）和一瓶毒药（可毒杀一人），"
            "每瓶药只能用一次。"
        ),
        GameRole.VILLAGER: (
            "你是村民，好人阵营的普通一员。"
            "没有特殊技能，靠推理和观察找出狼人。"
        ),
    }[role]

    return f"""
你是【{name}】，性格特点：{personality}。
在这场三国狼人杀游戏中，你的游戏身份是：{role.value}。

{role_tip}

重要规则：
1. 你只能通过对话和推理参与游戏，不要调用任何外部工具。
2. 白天讨论要以【{name}】的性格说话，符合人设。
3. 回复必须严格按要求的 JSON 格式输出，不要输出 JSON 以外的任何文字。
""".strip()


# ======================================================================
# 3. 自定义 Agent：继承 Agent，覆写 reply 即可
#    2.x 里 Agent 已经自带对话历史记忆，我们只管把 System Prompt 和模型喂进去
# ======================================================================

class PlayerAgent(Agent):
    """
    一个通用的"三国玩家"智能体。
    Agent 基类已经帮你做了：
      - 对话历史记忆（reply() 里自动把历史拼进 prompt）
      - 模型调用（self.model）
      - 流式输出（reply_stream()）
    我们只需要初始化时把 model 和 system_prompt 喂进去就行。
    """

    def __init__(self, name: str, role: GameRole, model):
        super().__init__(
            name=name,
            system_prompt=build_system_prompt(name, role),  # ← 2.x 叫 system_prompt，1.x 叫 sys_prompt
            model=model,
        )
        self.game_role = role
        self.character = name


# ======================================================================
# 4. 主持者：单独做一个 Agent，负责向所有玩家广播游戏进度
#    主持人不用太聪明，只要会发 Msg 就行
# ======================================================================

class ModeratorAgent(Agent):
    def __init__(self, model):
        super().__init__(
            name="游戏主持人",
            system_prompt=(
                "你是狼人杀游戏主持人，只负责向玩家播报游戏阶段和指令，"
                "不要回答任何玩家的推理或问题。"
            ),
            model=model,
        )

    def announce(self, text: str) -> Msg:
        """生成一条公告消息（主持人不调模型，直接返回 Msg 即可）"""
        return _m(self.name, text, role="assistant")


# ======================================================================
# 5. 游戏主控制器
# ======================================================================

class GameController:
    def __init__(self, players: List[PlayerAgent], moderator: ModeratorAgent):
        self.players   = players
        self.moderator  = moderator
        self.alive      = {p.name for p in players}     # 存活玩家集合
        self.werewolves = [p for p in players if p.game_role == GameRole.WEREWOLF]
        self.seer       = next(p for p in players if p.game_role == GameRole.SEER)
        self.witch      = next(p for p in players if p.game_role == GameRole.WITCH)
        self.witch_has_antidote = True
        self.witch_has_poison   = True

    @property
    def alive_players(self) -> List[PlayerAgent]:
        return [p for p in self.players if p.name in self.alive]

    def _format_alive(self) -> str:
        return "、".join(sorted(self.alive))

    async def run(self):
        print("\n🎮 欢迎来到三国狼人杀！\n" + "=" * 50)
        # 打印身份（正式游戏中不该打印，这里是学习用）
        for p in self.players:
            print(f"  {p.character} → {p.game_role.value}")

        for round_num in range(1, MAX_ROUND + 1):
            if self._check_win():
                break
            print(f"\n=== 第 {round_num} 轮游戏 ===")

            # 夜晚：狼人协商击杀 → 预言家查验 → 女巫救/毒
            killed_by_wolf = await self._werewolf_phase(round_num)
            check_result   = await self._seer_phase(round_num)
            final_deaths   = await self._witch_phase(killed_by_wolf)

            # 结算死亡
            for name in final_deaths:
                self.alive.discard(name)
                print(f"  💀 【{name}】倒下了")

            if self._check_win():
                break

            # 白天：全体讨论 + 投票
            await self._daytime_discussion(round_num)
            voted_out = await self._daytime_vote(round_num)
            if voted_out:
                self.alive.discard(voted_out)
                print(f"  🗳️ 投票淘汰 【{voted_out}】")

        print("\n🏁 游戏结束！")

    # ------------------------------------------------------------------
    # 5.1 狼人阶段
    # 教材里用 MsgHub(...) 建私密频道，2.x 里 MsgHub 移除了。
    # 这里用一个普通 List[Msg] 当"共享消息总线"来模拟：
    #   每轮讨论 → 把所有狼的 reply 追加进去 → 下一轮所有狼
    #   收到的就是完整的聊天历史。
    # ------------------------------------------------------------------
    async def _werewolf_phase(self, round_num: int) -> Optional[str]:
        alive_wolves = [w for w in self.werewolves if w.name in self.alive]
        if len(alive_wolves) < 1:
            return None

        print(f"\n🌙 第{round_num}夜 · 狼人阶段")

        # ---- 模拟 MsgHub：用一个列表当"私密聊天记录" ----
        wolf_chat: List[Msg] = [
            self.moderator.announce(
                f"🐺 狼人请睁眼，讨论今晚的击杀目标。"
                f" 存活玩家：{self._format_alive()}"
            )
        ]

        for _ in range(MAX_DISCUSSION_ROUND):
            for wolf in alive_wolves:
                try:
                    # 把聊天历史打包成一条"你收到的消息"传给 Agent
                    # 2.x 里 msg.content 是 list[TextBlock]，取第一个 TextBlock 的 .text
                    chat_history = "\n".join(
                        f"【{m.name}】{m.content[0].text if m.content else ''}"
                        for m in wolf_chat
                    )
                    prompt = _m(
                        "系统提醒",
                        f"以下是你们狼组目前的讨论记录：\n{chat_history}\n\n"
                        f"请结合上面的讨论，表达你的观点，并用 JSON 输出。",
                        role="user",
                    )
                    # smart_reply 同时拿到自然语言（打印用）和 final_msg（进聊天历史 + structured_output）
                    natural_text, reply = await smart_reply(wolf, prompt, structured_schema=DiscussionModel)
                    wolf_chat.append(reply)
                    display = natural_text[:80] if natural_text else "(无自然语言输出)"
                    print(f"  {wolf.character}: {display}...")
                except Exception as e:
                    print(f"  ⚠️ {wolf.name} 讨论时出错：{e}")

        # 投票阶段：并发让每个狼独立回答"我选谁"
        kill_prompt = _m("游戏主持人", "请根据刚才的讨论，投票选择今晚要击杀的目标。输出 JSON。")
        kill_msgs = await asyncio.gather(
            *[w.reply(kill_prompt, structured_schema=WerewolfKillModel)
              for w in alive_wolves]
        )

        # 统计谁被最多狼人选中
        votes = {}
        for msg in kill_msgs:
            try:
                # 2.x 的区别：structured_output 是 dict，需要手动 model_validate 成 pydantic 对象
                model = WerewolfKillModel.model_validate(msg.structured_output)
                votes[model.target_name] = votes.get(model.target_name, 0) + 1
            except Exception as e:
                print(f"  ⚠️ 解析狼人投票失败：{e}")

        if not votes:
            return None
        max_v = max(votes.values())
        top = [name for name, v in votes.items() if v == max_v]
        target = random.choice(top)
        print(f"  🎯 狼人统一击杀目标：【{target}】")
        return target

    # ------------------------------------------------------------------
    # 5.2 预言家阶段
    # ------------------------------------------------------------------
    async def _seer_phase(self, round_num: int):
        if self.seer.name not in self.alive:
            return
        print(f"\n🌙 第{round_num}夜 · 预言家阶段")

        alive_names = sorted(self.alive - {self.seer.name})
        prompt = _m(
            "游戏主持人",
            f"🔮 请选择一名要查验的玩家（只能是：{'、'.join(alive_names)}）。输出 JSON。",
        )
        try:
            reply = await self.seer.reply(prompt, structured_schema=SeerCheckModel)
            model = SeerCheckModel.model_validate(reply.structured_output)
            target_name = model.target_name
            is_wolf = any(w.name == target_name for w in self.werewolves)
            result = "狼人" if is_wolf else "好人"
            print(f"  🔍 预言家查验 【{target_name}】→ {result}")
        except Exception as e:
            print(f"  ⚠️ 预言家输出解析失败：{e}")

    # ------------------------------------------------------------------
    # 5.3 女巫阶段
    # ------------------------------------------------------------------
    async def _witch_phase(self, killed_by_wolf: Optional[str]) -> List[str]:
        if self.witch.name not in self.alive:
            return []
        print("\n🌙 夜晚 · 女巫阶段")

        info = f"今晚 【{killed_by_wolf}】 被狼人袭击了。" if killed_by_wolf else "今晚无人被袭击。"
        if not self.witch_has_antidote:
            info += " 你的解药已用完。"
        if not self.witch_has_poison:
            info += " 你的毒药已用完。"

        prompt = _m("游戏主持人", f"🧙‍♀️ {info} 请决定是否使用解药和毒药（输出 JSON）。")
        deaths: List[str] = []
        try:
            reply = await self.witch.reply(prompt, structured_schema=WitchActionModel)
            model = WitchActionModel.model_validate(reply.structured_output)
            if model.use_antidote and self.witch_has_antidote and killed_by_wolf:
                print(f"  ✅ 女巫使用解药救了 【{killed_by_wolf}】")
                self.witch_has_antidote = False
                killed_by_wolf = None
            if model.use_poison and self.witch_has_poison and model.poison_target:
                deaths.append(model.poison_target)
                self.witch_has_poison = False
                print(f"  ☠️ 女巫使用毒药毒了 【{model.poison_target}】")
        except Exception as e:
            print(f"  ⚠️ 女巫输出解析失败：{e}")

        if killed_by_wolf:
            deaths.append(killed_by_wolf)
        if not deaths:
            print("  🌤️ 昨夜平安无事。")
        return deaths

    # ------------------------------------------------------------------
    # 5.4 白天自由讨论（全员广播频道）
    # ------------------------------------------------------------------
    async def _daytime_discussion(self, round_num: int):
        print(f"\n☀️ 第{round_num}天 · 白天讨论")

        # ---- 模拟 MsgHub：全员共享聊天记录 ----
        all_chat: List[Msg] = [
            self.moderator.announce(
                f"☀️ 天亮了！现在开始自由讨论。"
                f" 存活玩家：{self._format_alive()}"
            )
        ]

        for _ in range(MAX_DISCUSSION_ROUND):
            for player in self.alive_players:
                try:
                    # 2.x 里 msg.content 是 list[TextBlock]，取第一个 TextBlock 的 .text
                    all_history = "\n".join(
                        f"【{m.name}】{m.content[0].text if m.content else ''}"
                        for m in all_chat
                    )
                    prompt = _m(
                        "系统提醒",
                        f"以下是目前所有人的发言记录：\n{all_history}\n\n"
                        f"请结合上面的讨论，说一下你的推理和怀疑对象，并用 JSON 输出。",
                        role="user",
                    )
                    natural_text, reply = await smart_reply(player, prompt, structured_schema=DiscussionModel)
                    all_chat.append(reply)
                    display = natural_text[:80] if natural_text else "(无自然语言输出)"
                    print(f"  {player.character}: {display}...")
                except Exception as e:
                    print(f"  ⚠️ {player.name} 发言时出错：{e}")

    # ------------------------------------------------------------------
    # 5.5 白天投票（asyncio.gather 替代 FanoutPipeline 并发收集）
    # ------------------------------------------------------------------
    async def _daytime_vote(self, round_num: int) -> Optional[str]:
        print(f"\n🗳️ 第{round_num}天 · 投票")
        alive_names = sorted(p.name for p in self.alive_players)

        vote_prompt = _m(
            "游戏主持人",
            f"请投票选出一名要淘汰的玩家。可选：{'、'.join(alive_names)}。输出 JSON。",
        )
        vote_msgs = await asyncio.gather(
            *[p.reply(vote_prompt, structured_schema=VoteModel)
              for p in self.alive_players]
        )

        tally: Dict[str, int] = {}
        for msg in vote_msgs:
            try:
                model = VoteModel.model_validate(msg.structured_output)
                tally[model.target_name] = tally.get(model.target_name, 0) + 1
                print(f"  {msg.name} 投给了 【{model.target_name}】")
            except Exception as e:
                print(f"  ⚠️ 解析投票失败：{e}")

        if not tally:
            return None
        max_v = max(tally.values())
        top = [name for name, v in tally.items() if v == max_v]
        return random.choice(top) if len(top) > 1 else top[0]

    # ------------------------------------------------------------------
    # 胜负判定
    # ------------------------------------------------------------------
    def _check_win(self) -> bool:
        alive_wolves = [w for w in self.werewolves if w.name in self.alive]
        alive_good   = [p for p in self.players
                        if p.name in self.alive and p.game_role != GameRole.WEREWOLF]
        if not alive_wolves:
            print("\n🎉 好人阵营获胜！狼人全灭。")
            return True
        if not alive_good:
            print("\n🐺 狼人阵营获胜！好人全灭。")
            return True
        return False


# ======================================================================
# 6. 入口
# ======================================================================

async def main():
    if not LLM_API_KEY:
        print("❌ 未检测到 LLM_API_KEY，请在 .env 中配置")
        return

    # 模型初始化
    # AgentScope 2.x 统一用 Credential 对象传递 API Key 和 base_url，
    # 不再直接在 ChatModel.__init__ 里传 api_key / base_url。
    credential = DeepSeekCredential.model_validate({
        "name": "deepseek",
        "type": "deepseek_credential",  # 必须是类名的 snake_case
        "api_key": LLM_API_KEY,
        "base_url": LLM_BASE_URL or "https://api.deepseek.com/v1",
    })
    model = DeepSeekChatModel(
        credential=credential,
        model=LLM_MODEL or "deepseek-chat",
    )

    # 创建玩家 Agent
    players: List[PlayerAgent] = [
        PlayerAgent(name=name, role=role, model=model)
        for name, role in CHARACTER_ASSIGNMENT.items()
    ]
    moderator = ModeratorAgent(model=model)

    # 启动游戏
    game = GameController(players=players, moderator=moderator)
    await game.run()


if __name__ == "__main__":
    asyncio.run(main())
