from __future__ import annotations

import base64
import logging
import re
from urllib.parse import quote

import httpx

from app.core.config import settings

log = logging.getLogger(__name__)


def providers_config() -> dict:
    """返回前端 /photo/config 需要的生图引擎配置状态（不暴露 Key）。"""
    gemini = {
        "configured": bool((settings.gemini_api_key or "").strip()),
        "name": "Gemini 3.1",
        "model": settings.gemini_model,
    }
    gpt_image2 = {
        "configured": bool((settings.gpt_image_api_key or "").strip()),
        "name": "GPT Image 2",
        "model": settings.gpt_image_model,
    }
    return {
        "configured": gemini["configured"] or gpt_image2["configured"],
        "providers": {"gemini": gemini, "gptImage2": gpt_image2},
    }


def _cinematic_look_prompt(costume: bool) -> str:
    keep = "" if costume else ", clothing"
    return (
        "Cinematic film look on top of the documentary photograph: shot at f/1.8 aperture, shallow depth of "
        "field, bokeh. Keep both people sharp and fully visible from head to shoes; apply the shallow focus and "
        "bokeh to the background, not to faces or bodies. Clean image, no noise, high dynamic range. Cinematic "
        "color grading, smooth color transitions, 10-bit color depth. Teal and Orange color palette. Perfect "
        "exposure, natural daylight 5600K, balanced lighting. Do not add film grain, heavy vignetting, letterbox "
        f"bars, or a color cast that changes identity{keep}, or architecture."
    )


def _visitor_costume_prompt() -> str:
    return (
        "COSTUME MODE applies only to the visitor. Do not change the sage's clothing, hat, robe, colors, fabric "
        "or accessories; keep the sage exactly as in Reference 2.\n\n"
        "Infer the visitor's apparent sex from Reference 1 and apply only subtle gendered tailoring of one shared "
        "Hanfu design. Replace the visitor's modern clothing and shoes with layered rustic beige / cream (米黄色) "
        "wide-sleeve Hanfu: cross-collar (交领) construction, brown edging along the collar and hems, a matching "
        "wide brown belt, and a flowing long skirt or robe with a trailing hem. Simple traditional cloth shoes "
        "with brown and beige details. If the visitor appears female, use a layered ruqun-style cut with a gently "
        "defined waist and a longer trailing skirt. If the visitor appears male, keep the same beige cloth, "
        "cross-collar, wide sleeves, brown belt and cloth shoes, but tailor it as a scholarly robe with a slightly "
        "shorter hem and less flared skirt drape. Do not add jewelry, hairpins, guan, wigs, or a second costume on "
        "the sage.\n\n"
        "Keep the visitor's original head, face, hairline and hairstyle exactly as in Reference 1. Do not restyle, "
        "bun, lengthen or ornament the hair. Keep identity, body proportions and the original facial expression.\n\n"
        "Ultra-realistic. Even shadowless lighting: no hard cast shadows, no dramatic contact shadows under the "
        "feet or on garment folds."
    )


def _composition_prompt(person: str, quote: str, pose: str | None, costume: bool = False) -> str:
    clothing_rule = (
        "Preserve the visitor's identity; do not beautify, age, slim, enlarge eyes, change skin tone, or create a "
        "generic face. Change only the visitor's clothing and shoes as specified below; keep the original hairstyle."
        if costume
        else
        "Preserve the visitor's identity; do not beautify, age, slim, enlarge eyes, change skin tone, change "
        "clothing or create a generic face."
    )
    lighting_rule = (
        "Match scale and perspective. Use even shadowless lighting."
        if costume
        else
        "Match scale, perspective and contact shadows."
    )
    costume_block = f" {_visitor_costume_prompt()}" if costume else ""
    clothing_ref = "" if costume else ", clothing"
    default_pose = (
        "The visitor stands solemnly close beside the sage, facing the camera, arms at the sides or hands folded "
        "in front, with no physical contact."
    )
    return (
        "Generate one extremely realistic, high-resolution documentary photograph for a Chinese academy "
        "cultural-tourism experience. The photograph should feel like a respectful commemorative portrait of a "
        "later-day visitor paying courtesy to a historical sage, not a casual souvenir with a friend.\n\n"
        "Reference 1 is the visitor full-body photo and is the authoritative identity, facial-expression, "
        f"body-proportion, height{clothing_ref} and hairstyle reference. Reference 2 is the fixed historical sage "
        f"{person}; preserve his face, age, beard, hat, robe, colors, identity, and dignified scholarly bearing. "
        "Reference 3 is the locked academy background; preserve its architecture, signboard, trees, stones, "
        "perspective and framing.\n\n"
        "Show exactly two people, the sage and the visitor, standing close together on the same ground plane as in "
        "a commemorative group photograph. Do not leave an exaggerated empty gap between them. The visitor is a "
        "respectful later-day guest or student, not a familiar companion. Do not let the visitor touch the sage: no "
        "hand on the shoulder, no linking arms, no holding hands, no hugging, no leaning, and no other physical "
        f"contact. {pose or default_pose}\n\n"
        "Reproduce the visitor's original facial expression exactly as shown in Reference 1, including gaze "
        "direction, eyelid openness, eyebrow position, mouth shape, lip separation, smile intensity and "
        "facial-muscle state. Do not add a smile, remove a smile, open or close the mouth, change the gaze, or "
        f"otherwise reinterpret the expression. {clothing_rule} Keep both full bodies visible from head to shoes. "
        f"{lighting_rule}{costume_block} {_cinematic_look_prompt(costume)} Do not add extra people, logos, "
        "watermarks or borders. Do not distort or repaint the architecture. The result must look like a real camera "
        f"photograph, not an illustration or synthetic portrait. Do not render this contextual quote: {quote}"
    )


def _face_refine_prompt(costume: bool = False) -> str:
    clothing_keep = (
        "Preserve the visitor Hanfu clothing, belt and shoes already present in Reference 1; do not restore modern "
        "clothing from Reference 3. Preserve visitor hair, head silhouette, hairstyle, body, hands, sage clothing, "
        "background, architecture, lighting, crop and composition from Reference 1."
        if costume
        else
        "Preserve all other pixels and content from Reference 1 as closely as possible: visitor hair, head "
        "silhouette, body, clothing, hands, sage, background, architecture, lighting, shadows, crop, composition, "
        "and the existing cinematic film look (f/1.8 shallow depth of field, background bokeh, clean "
        "high-dynamic-range image, cinematic teal-and-orange color grading, 5600K daylight exposure)."
    )
    clothing_ref = "" if costume else ", and clothing reference"
    return (
        "Localized identity-preserving facial-feature correction only. Reference 1 is the generated group "
        "photograph and is the authoritative edit target. Reference 2 is the visitor's face identity and exact "
        "expression reference; use it only for facial identity, facial proportions, skin complexion and expression. "
        "Reference 3 is the original visitor full-body photograph and is the body orientation, neck alignment and "
        f"hairstyle reference{clothing_ref}.\n\n"
        "In Reference 1, locate the modern visitor, not the historical sage. Keep the visitor's existing head "
        "position, head size, yaw, pitch, roll, camera perspective, neck position, shoulder alignment and body "
        "direction exactly as they appear in Reference 1. Do not paste or transplant the entire head from "
        "Reference 2. Do not copy Reference 2's camera angle, head angle, focal length, exposure, white balance, "
        "indoor lighting or background. Adapt the identity and expression from Reference 2 onto the existing head "
        "geometry in Reference 1.\n\n"
        "Correct only the modern visitor's internal facial features and the minimum surrounding skin needed for a "
        "seamless blend. Preserve the exact expression from Reference 2: eye openness, eyebrow state, mouth shape, "
        "lip separation and smile intensity, but render that expression in the head orientation and perspective "
        "already established by Reference 1. Preserve facial structure, eye shape and spacing, nose, lips, jawline, "
        "natural asymmetry and apparent age. Keep the visitor's original hairstyle and hairline. Keep the visitor's "
        "intrinsic skin complexion from References 2 and 3, while applying the scene illumination, color "
        "temperature, exposure and shadow direction from Reference 1. The face, ears, jaw, hairline and neck must "
        "have a continuous natural skin-tone transition with no mask edge, pasted-face boundary, halo, color patch "
        "or mismatched sharpness.\n\n"
        "Do not beautify, enlarge eyes, narrow the jaw, smooth skin excessively or create a generic face. "
        f"{clothing_keep} Do not flatten contrast, add noise, or change white balance. Output the complete "
        "corrected group photograph with no text or added objects."
    )


def _parse_data_url(data_url: str) -> tuple[str, str]:
    if ";base64," not in data_url:
        raise ValueError("参考图格式无效")
    head, b64 = data_url.split(";base64,", 1)
    mime = head.split(":", 1)[1]
    if not mime or not b64:
        raise ValueError("参考图格式无效")
    return mime, b64


def _extract_image(payload: dict) -> str | None:
    if not isinstance(payload, dict):
        return None

    # OpenAI images style: data[0].b64_json / url
    data = payload.get("data")
    if isinstance(data, list) and data and isinstance(data[0], dict):
        first = data[0]
        if first.get("b64_json"):
            return "data:image/png;base64," + first["b64_json"]
        if first.get("url"):
            return first["url"]

    # OpenAI chat style: choices[0].message
    choices = payload.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        msg = choices[0].get("message") or {}
        if not isinstance(msg, dict):
            msg = {}
        content = msg.get("content")
        if isinstance(content, str):
            if content.startswith("data:image/") or content.startswith("http"):
                return content
            m = re.search(
                r"https?://[^\s)\"']+|data:image/[a-zA-Z0-9.+-]+;base64,[a-zA-Z0-9+/=]+",
                content,
            )
            if m:
                return m.group(0)
        if isinstance(content, list):
            for part in content:
                found = _part_image(part)
                if found:
                    return found
        images = msg.get("images")
        if isinstance(images, list) and images:
            found = _part_image(images[0])
            if found:
                return found

    # Gemini native: candidates[].content.parts[].inlineData
    candidates = payload.get("candidates")
    if isinstance(candidates, list):
        for cand in candidates:
            if not isinstance(cand, dict):
                continue
            content = cand.get("content")
            if not isinstance(content, dict):
                continue
            parts = content.get("parts")
            if isinstance(parts, list):
                for part in parts:
                    found = _part_image(part)
                    if found:
                        return found

    if payload.get("image"):
        return payload["image"]
    if payload.get("image_url"):
        return payload["image_url"]
    return None


def _part_image(part) -> str | None:
    if not isinstance(part, dict):
        return None
    if part.get("type") == "image_url":
        iu = part.get("image_url")
        if isinstance(iu, dict):
            if iu.get("url"):
                return iu["url"]
            if iu.get("data"):
                return "data:image/png;base64," + iu["data"]
        elif isinstance(iu, str):
            return iu
    inline = part.get("inlineData") or part.get("inline_data")
    if isinstance(inline, dict) and inline.get("data"):
        mime = inline.get("mimeType") or inline.get("mime_type") or "image/png"
        return f"data:{mime};base64,{inline['data']}"
    if part.get("b64_json"):
        return "data:image/png;base64," + part["b64_json"]
    image_url = part.get("image_url")
    if isinstance(image_url, str) and image_url:
        return image_url
    if part.get("url"):
        return part["url"]
    return None


async def _ensure_data_url(client: httpx.AsyncClient, image: str) -> str:
    if image.startswith("data:image/"):
        return image
    if not (image.startswith("http://") or image.startswith("https://")):
        raise RuntimeError("生图服务返回了无法识别的图片格式")
    resp = await client.get(image)
    if resp.status_code >= 400:
        raise RuntimeError(f"生成图片下载失败：{resp.status_code}")
    mime = (resp.headers.get("content-type") or "image/png").split(";")[0]
    return "data:" + mime + ";base64," + base64.b64encode(resp.content).decode("ascii")


async def _request_google_image(
    client: httpx.AsyncClient,
    prompt: str,
    refs: list[dict],
    stage: str,
    person: str,
) -> str:
    url = (
        f"{settings.gemini_api_base_url}/models/{quote(settings.gemini_model, safe='')}"
        f":generateContent?key={quote(settings.gemini_api_key, safe='')}"
    )
    parts: list[dict] = [{"text": prompt}]
    for ref in refs:
        mime, b64 = _parse_data_url(ref["dataUrl"])
        parts.append({"text": ref["label"]})
        parts.append({"inlineData": {"mimeType": mime, "data": b64}})
    body = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
    }
    log.info("[gemini] request stage=%s model=%s person=%s", stage, settings.gemini_model, person)
    resp = await client.post(url, json=body, headers={"Content-Type": "application/json"})
    if resp.status_code >= 400:
        raise RuntimeError(f"中转站返回 {resp.status_code}: {resp.text[:500]}")
    out = _extract_image(resp.json())
    if not out:
        raise RuntimeError("Gemini 返回中没有找到图片数据")
    return out


async def _request_openai_image(
    client: httpx.AsyncClient,
    prompt: str,
    refs: list[dict],
) -> str:
    endpoint = settings.gemini_openai_path
    url = f"{settings.gemini_api_base_url}{endpoint if endpoint.startswith('/') else '/' + endpoint}"
    # 该中转站的 gemini 适配层要求同时提供 OpenAI 风格的 messages 与 Gemini 原生的 contents，
    # 少任意一个都会返回 500 "contents is required" / "messages is required"。
    content: list[dict] = [{"type": "text", "text": prompt}]
    parts: list[dict] = [{"text": prompt}]
    for ref in refs:
        if ref.get("label"):
            content.append({"type": "text", "text": ref["label"]})
            parts.append({"text": ref["label"]})
        content.append({"type": "image_url", "image_url": {"url": ref["dataUrl"]}})
        mime, b64 = _parse_data_url(ref["dataUrl"])
        parts.append({"inlineData": {"mimeType": mime, "data": b64}})
    body = {
        "model": settings.gemini_model,
        "messages": [{"role": "user", "content": content}],
        "contents": [{"role": "user", "parts": parts}],
        "modalities": ["text", "image"],
    }
    resp = await client.post(
        url,
        json=body,
        headers={"Authorization": f"Bearer {settings.gemini_api_key}"},
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"中转站返回 {resp.status_code}: {resp.text[:500]}")
    out = _extract_image(resp.json())
    if not out:
        raise RuntimeError("Gemini 返回中没有找到图片数据")
    return out


async def stream_generate_photo(payload: dict):
    """按真实处理阶段 yield 进度事件，最后一个事件包含 image。"""
    visitor = payload.get("visitorImage")
    face = payload.get("faceImage")
    poet = payload.get("poetImage")
    background = payload.get("backgroundImage")
    person = payload.get("person") or ""
    quote = payload.get("quote") or ""
    pose = payload.get("pose")
    costume = bool(payload.get("costume"))

    for name, value in (("visitorImage", visitor), ("poetImage", poet), ("backgroundImage", background)):
        if not isinstance(value, str) or not value.startswith("data:image/"):
            raise ValueError(f"缺少参考图：{name}")
    if not (settings.gemini_api_key or "").strip():
        raise RuntimeError("未配置 GEMINI_API_KEY")

    style = (settings.gemini_api_style or "google").lower()
    has_face = isinstance(face, str) and face.startswith("data:image/")

    yield {"progress": 10, "message": "正在准备提示词与参考图"}
    comp_prompt = _composition_prompt(person, quote, pose, costume)
    comp_refs = [
        {"label": "REFERENCE 1 - VISITOR FULL-BODY AND IDENTITY PHOTO", "dataUrl": visitor},
        {"label": "REFERENCE 2 - FIXED POET CHARACTER MASTER", "dataUrl": poet},
        {"label": "REFERENCE 3 - LOCKED ACADEMY BACKGROUND", "dataUrl": background},
    ]

    async with httpx.AsyncClient(timeout=httpx.Timeout(180.0, connect=20.0)) as client:
        yield {"progress": 30, "message": "已提交生成模型，正在生成合照（通常 15–30 秒）"}
        if style == "google":
            output = await _request_google_image(client, comp_prompt, comp_refs, "composition", person)
        else:
            output = await _request_openai_image(client, comp_prompt, comp_refs)

        yield {"progress": 88, "message": "合照已生成"}

        if has_face:
            yield {"progress": 90, "message": "正在精修面部"}
            refine_refs = [
                {"label": "REFERENCE 1 - GENERATED GROUP PHOTO / AUTHORITATIVE EDIT TARGET AND HEAD GEOMETRY", "dataUrl": output},
                {"label": "REFERENCE 2 - VISITOR FACE IDENTITY AND EXACT EXPRESSION ONLY", "dataUrl": face},
                {"label": "REFERENCE 3 - ORIGINAL VISITOR FULL-BODY / BODY DIRECTION, NECK, HAIR AND CLOTHING", "dataUrl": visitor},
            ]
            if style == "google":
                output = await _request_google_image(
                    client, _face_refine_prompt(costume), refine_refs, "face-refine", person
                )
            else:
                output = await _request_openai_image(client, _face_refine_prompt(costume), refine_refs)
            yield {"progress": 96, "message": "面部精修完成"}

        final = await _ensure_data_url(client, output)
        yield {"progress": 100, "message": "生成完成", "image": final}
