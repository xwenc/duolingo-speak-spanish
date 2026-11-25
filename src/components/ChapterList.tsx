import { useEffect, useState } from 'react';
import { formatPracticeAge } from '../utils/practiceAge';
import type { ChapterProgress } from '../services/api';
import { ArrowLeft, ArrowRight, Layers } from 'lucide-react';
import type { Book } from '../data/books';

interface Props {
  book: Book;
  progress: Record<string, ChapterProgress>;
  onBack: () => void;
  onSelectChapter: (id: string) => void;
}

export function ChapterList({ book, progress, onBack, onSelectChapter }: Props) {
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 30_000);
    return () => window.clearInterval(timer);
  }, []);
  return <main className="w-full max-w-6xl mx-auto px-5 py-8">
    <button onClick={onBack} className="flex items-center gap-2 text-slate-500 font-bold hover:text-sky-600"><ArrowLeft size={20} />返回教材馆</button>
    <div className="my-8">
      <p className="text-[#58a700] font-black mb-2">{book.title}</p>
      <h1 className="text-3xl font-black text-slate-700">章节列表</h1>
      <p className="mt-3 text-slate-500">选择一个章节，开始口语练习。</p>
    </div>
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {book.chapters.map((chapter, index) => {
        const saved = progress[chapter.id];
        const count = book.exercises.filter(exercise => exercise.unitId === chapter.id).length;
        return <button key={chapter.id} disabled={!count} onClick={() => onSelectChapter(chapter.id)} className="flex items-center gap-3 min-w-0 text-left bg-white rounded-2xl border-2 border-b-[5px] border-slate-200 p-5 enabled:hover:border-[#58cc02] disabled:opacity-50 disabled:cursor-not-allowed">
          <span className="w-12 h-12 shrink-0 rounded-xl bg-sky-50 text-sky-600 flex items-center justify-center">{chapter.icon ? <span className="text-2xl">{chapter.icon}</span> : <Layers size={24} />}</span>
          <span className="flex-1 min-w-0"><span className="text-xs font-bold text-slate-400">第 {index + 1} 章</span><span className="block font-black text-lg text-slate-700 break-words">{chapter.name}</span><span className="text-sm text-slate-500">{count ? `${count} 句口语练习` : '暂无句子'}</span><span className="mt-3 flex flex-wrap gap-x-3 gap-y-1 text-xs"><span className="font-bold text-[#58a700]" title="已练句子最近一次得分的平均值（满分 100）">{saved ? `平均得分 ${saved.averageScore} 分 · 已练 ${saved.practicedCount}/${count} 句` : '暂无得分'}</span><span className="text-slate-400" title={saved ? new Date(saved.lastPracticedAt).toLocaleString() : undefined}>{saved ? `上次练习：${formatPracticeAge(saved.lastPracticedAt, now)}` : '尚未练习'}</span></span></span>
          <ArrowRight size={20} className="shrink-0 text-slate-400" />
        </button>;
      })}
      {!book.chapters.length && <p className="col-span-full p-8 text-center text-slate-500">暂无章节</p>}
    </div>
    {book.exercises.length > 0 && <button onClick={() => onSelectChapter('all')} className="mt-6 w-full rounded-2xl border-2 border-b-4 border-[#58a700] bg-[#58cc02] p-4 font-black text-white">全部章节综合练习 · {book.exercises.length} 句</button>}
  </main>;
}
