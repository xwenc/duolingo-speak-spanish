import { useEffect, useState } from 'react';
import { api } from '../services/api';

type Day = { date: string; count: number; accuracy: number | null };
type Report = { daily: Day[]; timezone: string; total: number; accuracy: number | null; activeDays: number };
const percent = (value: number | null) => value === null ? '—' : `${value}%`;

function TrendChart({ daily, metric }: { daily: Day[]; metric: 'count' | 'accuracy' }) {
  const accuracy = metric === 'accuracy';
  const title = accuracy ? '每日准确率' : '每日完成数量';
  const color = accuracy ? '#0284c7' : '#58a700';
  const max = accuracy ? 100 : Math.max(4, ...daily.map(day => day.count));
  const x = (i: number) => 52 + i * 620 / Math.max(1, daily.length - 1);
  const y = (value: number) => 205 - value / max * 175;
  // A missing accuracy is a gap, rather than an incorrect zero score.
  let path = '';
  let connected = false;
  daily.forEach((day, i) => {
    const value = day[metric];
    if (value === null) { connected = false; return; }
    path += `${connected ? ' L' : ' M'}${x(i)},${y(value)}`;
    connected = true;
  });
  return <section className="rounded-3xl border-2 border-slate-200 bg-white p-4 sm:p-6">
    <h2 className="font-black text-xl text-slate-700">{title}<span className="ml-2 text-sm font-normal text-slate-500">{accuracy ? '（%）' : '（次）'}</span></h2>
    <svg viewBox="0 0 700 250" role="img" aria-label={`${title}曲线图，详细数据见下方每日明细`} className="w-full mt-4">
      {[0, 1, 2, 3, 4].map(i => <g key={i}>
        <line x1="52" x2="672" y1={y(max * i / 4)} y2={y(max * i / 4)} stroke="#e2e8f0" strokeDasharray="4 4" />
        <text x="42" y={y(max * i / 4) + 5} textAnchor="end" fontSize="14" fill="#64748b">{Math.round(max * i / 4)}</text>
      </g>)}
      <path d={path} stroke={color} strokeWidth="3" strokeLinejoin="round" strokeLinecap="round" fill="none" />
      {daily.map((day, i) => day[metric] !== null && <circle key={day.date} cx={x(i)} cy={y(day[metric]!)} r={daily.length > 30 ? 2 : 4} fill={color}>
        <title>{day.date}：{accuracy ? percent(day.accuracy) : `${day.count} 次`}</title>
      </circle>)}
      {[0, Math.floor((daily.length - 1) / 2), daily.length - 1].map((i, index) => <text key={index} x={x(i)} y="236" textAnchor="middle" fontSize="14" fill="#64748b">{daily[i]?.date.slice(5)}</text>)}
    </svg>
  </section>;
}

export function ReportPage({ onBack }: { onBack: () => void }) {
  const [days, setDays] = useState(30);
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true;
    setReport(null); setError('');
    const zone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
    api<Report>(`/report?days=${days}&timezone=${encodeURIComponent(zone)}`)
      .then(data => { if (active) setReport(data); })
      .catch(err => { if (active) setError((err as Error).message); });
    return () => { active = false; };
  }, [days, retry]);
  return <main className="w-full max-w-5xl mx-auto px-4 py-8 sm:px-6">
    <button onClick={onBack} className="font-bold text-[#58a700] mb-6 hover:underline">返回教材馆</button>
    <div className="flex flex-wrap justify-between gap-4 items-center mb-6">
      <div><p className="font-bold text-[#58a700] mb-2">每一次练习，都有进步</p><h1 className="text-3xl font-black text-slate-700">学习报告</h1></div>
      <div className="flex gap-2" role="group" aria-label="统计时间范围">{[7, 30, 90].map(value => <button key={value} onClick={() => setDays(value)} aria-pressed={days === value} className={`rounded-xl border-2 px-3 py-2 font-bold ${days === value ? 'border-[#58a700] bg-lime-50 text-[#58a700]' : 'border-slate-200 bg-white text-slate-500'}`}>近 {value} 天</button>)}</div>
    </div>
    <p className="text-slate-500 mb-6">数量按已提交练习次数统计，含重练与跳过；准确率为当日所有提交评分的平均值，无练习时不计算。</p>
    {error ? <div role="alert" className="rounded-2xl bg-red-50 p-5 text-red-700">{error}<button onClick={() => setRetry(v => v + 1)} className="ml-4 underline font-bold">重试</button></div> : !report ? <p role="status">正在加载学习报告…</p> : <>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">{[
        ['完成练习', `${report.total} 次`], ['平均准确率', percent(report.accuracy)], ['练习天数', `${report.activeDays} 天`],
      ].map(([label, value]) => <div key={label} className="bg-white border-2 border-slate-200 rounded-2xl p-5"><p className="text-slate-500">{label}</p><p className="text-3xl font-black text-slate-700 mt-2">{value}</p></div>)}</div>
      {!report.total && <p role="status" className="rounded-2xl bg-lime-50 p-5 mb-6 text-[#58a700]">这段时间还没有练习记录。完成一次练习后，就能看到你的学习曲线。</p>}
      <div className="grid gap-6"><TrendChart daily={report.daily} metric="count" /><TrendChart daily={report.daily} metric="accuracy" /></div>
      <p className="text-sm text-slate-500 mt-4">统计时区：{report.timezone} · 无练习日期的准确率显示为「—」。</p>
      <details className="mt-6 rounded-2xl border-2 border-slate-200 bg-white p-5"><summary className="cursor-pointer font-bold text-slate-700">每日明细</summary>
        <table className="w-full text-left mt-4"><caption className="sr-only">每天完成练习数量与准确率</caption><thead><tr className="border-b text-slate-500"><th className="py-3">日期</th><th>完成数量</th><th>准确率</th></tr></thead><tbody>{[...report.daily].reverse().map(day => <tr key={day.date} className="border-b border-slate-100"><th scope="row" className="py-3 font-normal">{day.date}</th><td>{day.count} 次</td><td>{percent(day.accuracy)}</td></tr>)}</tbody></table>
      </details>
    </>}
  </main>;
}
