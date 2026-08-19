from fastapi import APIRouter

from app.services.figures import list_figures

router = APIRouter(prefix="/figures", tags=["figures"])


@router.get("")
async def get_figures():
    """历史名人列表（身份提示词、画像、生平、起始问题）。公开官网内容，无需登录；
    点击「开始对话」后的问答经 /agent/stream（需登录）进行。"""
    return list_figures()
