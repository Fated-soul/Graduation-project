from __future__ import annotations

from html import escape
import json
from typing import Any

import streamlit.components.v1 as components


def render_synchronized_player(
    *,
    video_url: str | None,
    duration_seconds: float | None,
    modeling_events: list[dict[str, Any]],
    signal_windows: list[dict[str, Any]],
    annotations: list[dict[str, Any]],
    session_type: str = "fear_conditioning",
    compact: bool = False,
) -> None:
    duration = _resolve_duration(duration_seconds, modeling_events, signal_windows, annotations)
    payload = {
        "duration": duration,
        "sessionType": session_type,
        "events": [
            {
                "type": item.get("event_type") or "behavior_state",
                "label": item.get("event_label") or "造模事件",
                "start": float(item.get("start_time_seconds") or 0),
                "stop": float(item.get("stop_time_seconds") or item.get("start_time_seconds") or 0),
                "value": item.get("numeric_value"),
                "unit": item.get("unit") or "",
            }
            for item in modeling_events
        ],
        "signals": [
            {
                "modality": item.get("modality") or "motion",
                "name": item.get("signal_name") or "多模态信号",
                "time": (
                    float(item.get("window_start_seconds") or 0)
                    + float(item.get("window_end_seconds") or 0)
                ) / 2,
                "value": float(item.get("mean_value") or 0),
                "unit": item.get("unit") or "",
            }
            for item in signal_windows
        ],
        "annotations": [
            {
                "time": float(item.get("timestamp_seconds") or 0),
                "category": item.get("category") or "人工复核",
                "note": item.get("note") or "",
            }
            for item in annotations
            if item.get("timestamp_seconds") is not None
        ],
    }
    data_json = json.dumps(payload, ensure_ascii=False, default=str).replace("</", "<\\/")
    video_html = (
        f'<video id="sessionVideo" controls preload="metadata" playsinline '
        f'src="{escape(video_url, quote=True)}"></video>'
        if video_url
        else '<div class="video-empty">本次会话没有行为视频，仍可复核其他模态证据</div>'
    )
    html = _PLAYER_HTML.replace("__VIDEO__", video_html).replace("__PAYLOAD__", data_json)
    html = html.replace("__VIDEO_HEIGHT__", "285px" if compact else "390px")
    components.html(html, height=735 if compact else 840, scrolling=False)


def _resolve_duration(
    stored_duration: float | None,
    events: list[dict[str, Any]],
    signals: list[dict[str, Any]],
    annotations: list[dict[str, Any]],
) -> float:
    values = [float(stored_duration or 0)]
    values.extend(float(item.get("stop_time_seconds") or item.get("start_time_seconds") or 0) for item in events)
    values.extend(float(item.get("window_end_seconds") or 0) for item in signals)
    values.extend(
        float(item.get("timestamp_seconds") or 0)
        for item in annotations
        if item.get("timestamp_seconds") is not None
    )
    return max(1.0, max(values, default=1.0))


_PLAYER_HTML = r"""
<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><style>
*{box-sizing:border-box}body{margin:0;color:#1f3347;background:transparent;font-family:Arial,"Microsoft YaHei",sans-serif}
.workspace{overflow:hidden;border:1px solid #dbe3ea;border-radius:8px;background:#fff}
.video-shell{display:flex;min-height:240px;align-items:center;justify-content:center;background:#0f1720}
video{display:block;width:100%;height:__VIDEO_HEIGHT__;object-fit:contain;background:#0f1720}
.video-empty{color:#b8c4ce;font-size:14px}.panel{padding:13px 16px 15px}.toolbar{display:flex;justify-content:space-between;margin-bottom:8px}
.readout{color:#075f82;font-size:13px;font-variant-numeric:tabular-nums}canvas{display:block;width:100%;height:320px;border:1px solid #e1e8ee;border-radius:6px;background:#f8fafc;cursor:crosshair}
.scrubber{width:100%;margin:8px 0 4px;accent-color:#087eae}.legend{display:flex;gap:15px;flex-wrap:wrap;color:#66788a;font-size:12px}
.legend span:before{display:inline-block;width:9px;height:9px;margin-right:5px;border-radius:2px;content:""}.shock:before{background:#dc4b4b}.freeze:before{background:#11a4a1}.calcium:before{background:#7656c7}.physio:before{background:#1688c4}.annotation:before{background:#e39728}
.detail{min-height:38px;margin-top:9px;padding:8px 10px;border-left:3px solid #8fc4d8;color:#52697d;background:#f6fafc;font-size:12px;line-height:1.55}
</style></head><body><div class="workspace"><div class="video-shell">__VIDEO__</div><div class="panel">
<div class="toolbar"><strong>多模态同步时间轴</strong><span id="readout" class="readout">00:00.0 / 00:00.0</span></div>
<canvas id="timeline" aria-label="多模态造模证据时间轴"></canvas><input id="scrubber" class="scrubber" type="range" min="0" step="0.1" value="0">
<div class="legend"><span class="shock">足底电击</span><span class="freeze">冻结/状态事件</span><span class="calcium">钙活动</span><span class="physio">运动与生理信号</span><span class="annotation">人工复核</span></div>
<div id="detail" class="detail">点击时间轴可跳转至相应影像位置，移动鼠标可查看证据。</div></div></div>
<script>
const data=__PAYLOAD__, canvas=document.getElementById('timeline'),ctx=canvas.getContext('2d'),video=document.getElementById('sessionVideo'),scrubber=document.getElementById('scrubber'),readout=document.getElementById('readout'),detail=document.getElementById('detail');
let duration=Math.max(1,Number(data.duration||1)),currentTime=0,geometry=null;scrubber.max=String(duration);
function fmt(s){s=Math.max(0,Number(s||0));const m=Math.floor(s/60),r=s-m*60;return String(m).padStart(2,'0')+':'+r.toFixed(1).padStart(4,'0')}
function xFor(t,l,w){return l+Math.max(0,Math.min(duration,t))/duration*w}
function normalized(points,value){const vals=points.map(p=>Number(p.value)).filter(Number.isFinite),lo=Math.min(...vals),hi=Math.max(...vals);return (Number(value)-lo)/Math.max(.000001,hi-lo)}
function resize(){const rect=canvas.getBoundingClientRect(),ratio=window.devicePixelRatio||1;canvas.width=Math.max(1,Math.round(rect.width*ratio));canvas.height=Math.max(1,Math.round(rect.height*ratio));ctx.setTransform(ratio,0,0,ratio,0,0);draw()}
function line(points,yTop,yBottom,color,l,w){if(!points.length)return;ctx.strokeStyle=color;ctx.lineWidth=2;ctx.beginPath();points.forEach((p,i)=>{const x=xFor(Number(p.time),l,w),y=yBottom-normalized(points,p.value)*(yBottom-yTop);if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y)});ctx.stroke()}
function draw(){const width=canvas.clientWidth,height=canvas.clientHeight,left=112,right=18,w=Math.max(10,width-left-right);geometry={left,w};ctx.clearRect(0,0,width,height);ctx.fillStyle='#f8fafc';ctx.fillRect(0,0,width,height);ctx.font='12px Arial,Microsoft YaHei,sans-serif';ctx.textAlign='right';ctx.textBaseline='middle';ctx.fillStyle='#60758a';const offline=data.sessionType==='offline_consolidation',fc=data.sessionType==='fear_conditioning',labels=offline?[['睡眠状态',42],['钙活动',98],['脑电',154],['肌电',210],['人工复核',266]]:[[fc?'刺激与冻结':'行为与状态',42],['钙活动',98],['运动',154],['其他生理信号',210],['人工复核',266]];labels.forEach(v=>ctx.fillText(v[0],left-12,v[1]));
ctx.strokeStyle='#dce5ec';ctx.textAlign='center';ctx.textBaseline='top';for(let i=0;i<=5;i++){const sec=duration*i/5,x=xFor(sec,left,w);ctx.beginPath();ctx.moveTo(x,18);ctx.lineTo(x,276);ctx.stroke();ctx.fillStyle='#74869a';ctx.fillText(fmt(sec),x,282)}
for(const e of data.events){const sx=xFor(Number(e.start),left,w),ex=xFor(Math.max(Number(e.start),Number(e.stop)),left,w),active=currentTime>=Number(e.start)&&currentTime<=Number(e.stop);ctx.fillStyle=e.type==='electric_shock'?(active?'#b62f2f':'#dc4b4b'):(active?'#087b79':'#24aaa7');ctx.fillRect(sx,34,Math.max(4,ex-sx),18)}
const calcium=data.signals.filter(p=>p.modality==='calcium'),motion=data.signals.filter(p=>p.modality==='motion'),eeg=data.signals.filter(p=>p.modality==='eeg'),emg=data.signals.filter(p=>p.modality==='emg');line(calcium,73,119,'#7656c7',left,w);if(offline){line(eeg,129,175,'#169b6b',left,w);line(emg,185,231,'#d27b19',left,w)}else{line(motion,129,175,'#1688c4',left,w);line(eeg,185,231,'#169b6b',left,w);line(emg,185,231,'#d27b19',left,w)}
for(const note of data.annotations){const x=xFor(Number(note.time),left,w);ctx.fillStyle='#e39728';ctx.beginPath();ctx.moveTo(x,248);ctx.lineTo(x-6,266);ctx.lineTo(x+6,266);ctx.closePath();ctx.fill()}
const play=xFor(currentTime,left,w);ctx.strokeStyle='#d84343';ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(play,17);ctx.lineTo(play,276);ctx.stroke();ctx.fillStyle='#d84343';ctx.beginPath();ctx.arc(play,17,4,0,Math.PI*2);ctx.fill();readout.textContent=fmt(currentTime)+' / '+fmt(duration)}
function seek(s){currentTime=Math.max(0,Math.min(duration,Number(s||0)));scrubber.value=String(currentTime);if(video&&Number.isFinite(video.duration))video.currentTime=currentTime;draw()}
canvas.addEventListener('click',e=>{const r=canvas.getBoundingClientRect();seek(Math.max(0,Math.min(1,(e.clientX-r.left-geometry.left)/geometry.w))*duration)});
canvas.addEventListener('mousemove',e=>{const r=canvas.getBoundingClientRect(),x=e.clientX-r.left,y=e.clientY-r.top,time=Math.max(0,Math.min(duration,(x-geometry.left)/geometry.w*duration));let msg=fmt(time)+' · 点击可跳转至此位置';const ev=data.events.find(v=>y>=28&&y<=58&&time>=Number(v.start)&&time<=Math.max(Number(v.start),Number(v.stop)));if(ev)msg=ev.label+'：'+fmt(ev.start)+' 至 '+fmt(ev.stop)+(ev.value!==null&&ev.value!==undefined?' · '+ev.value+' '+ev.unit:'');else if(y>=68&&y<=236&&data.signals.length){let lane=y<124?'calcium':(y<180?(data.sessionType==='offline_consolidation'?'eeg':'motion'):(data.sessionType==='offline_consolidation'?'emg':null)),candidates=data.signals.filter(v=>!lane||v.modality===lane);if(candidates.length){const n=candidates.reduce((a,b)=>Math.abs(Number(b.time)-time)<Math.abs(Number(a.time)-time)?b:a);msg=n.name+'：'+Number(n.value).toFixed(3)+' '+n.unit+' · '+fmt(n.time)}}detail.textContent=msg});
canvas.addEventListener('mouseleave',()=>detail.textContent='点击时间轴可跳转至相应影像位置，移动鼠标可查看证据。');scrubber.addEventListener('input',()=>seek(scrubber.value));if(video){video.addEventListener('timeupdate',()=>{currentTime=Math.min(video.currentTime,duration);scrubber.value=String(currentTime);draw()});video.addEventListener('error',()=>detail.textContent='当前浏览器无法直接解码该视频格式，可使用页面中的原始影像入口。')}
window.addEventListener('resize',resize);resize();
</script></body></html>
"""
