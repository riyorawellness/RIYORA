import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { QUIZ } from "@/mock/data";
import { TID } from "@/constants/testIds";

export default function Assessment() {
  const nav = useNavigate();
  const { id } = useParams();
  const questions = QUIZ.questions;
  const [current, setCurrent] = useState(0);
  const [answers, setAnswers] = useState(Array(questions.length).fill(null));

  const progress = useMemo(() => Math.round(((current + 1) / questions.length) * 100), [current, questions.length]);
  const q = questions[current];

  const select = (idx) => setAnswers((a) => a.map((v, i) => (i === current ? idx : v)));

  const submit = () => {
    if (answers.some((a) => a === null)) return toast.error("Please answer all questions");
    const marks = answers.reduce((n, a, i) => (a === questions[i].correct_index ? n + 1 : n), 0);
    const passed = marks === questions.length;
    toast[passed ? "success" : "error"](`Score ${marks}/${questions.length} — ${passed ? "passed" : "try again"}`);
    if (passed) nav(`/app/certificate/${id}`, { replace: true });
  };

  return (
    <div className="min-h-screen bg-white">
      <div className="rw-phone rw-safe-top px-5 pb-8 pt-5">
        <button
          onClick={() => nav(-1)}
          className="grid h-9 w-9 place-items-center rounded-full hover:bg-[hsl(var(--rw-grey-50))]"
        >
          <ChevronLeft className="h-5 w-5 text-[hsl(var(--rw-royal-deep))]" />
        </button>

        <p className="mt-5 rw-eyebrow">{QUIZ.title}</p>
        <h1 className="mt-1 rw-serif text-3xl">Question {current + 1} of {questions.length}</h1>

        <div className="mt-4" data-testid={TID.quizProgress}>
          <div className="relative h-1.5 rounded-full bg-[hsl(var(--rw-grey-100))]">
            <div
              className="absolute inset-y-0 left-0 rounded-full bg-[hsl(var(--rw-royal))]"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="mt-1 text-[10px] uppercase tracking-widest text-muted-foreground">{progress}% complete</div>
        </div>

        <div className="mt-8 rw-card p-5">
          <p className="rw-serif text-xl text-foreground">{q.q}</p>
          <div className="mt-5 space-y-2">
            {q.options.map((opt, i) => {
              const isSelected = answers[current] === i;
              return (
                <button
                  key={opt}
                  onClick={() => select(i)}
                  data-testid={`quiz-option-${i}`}
                  className={`flex w-full items-center justify-between rounded-2xl border p-4 text-left text-sm transition-all ${
                    isSelected
                      ? "border-[hsl(var(--rw-royal))] bg-[hsl(var(--rw-sky-soft))] text-[hsl(var(--rw-royal-deep))]"
                      : "border-[hsl(var(--rw-grey-100))] hover:bg-[hsl(var(--rw-grey-50))]"
                  }`}
                >
                  <span className="pr-3">{opt}</span>
                  <span
                    className={`grid h-6 w-6 place-items-center rounded-full border ${
                      isSelected
                        ? "border-[hsl(var(--rw-royal))] bg-[hsl(var(--rw-royal))] text-white"
                        : "border-[hsl(var(--rw-grey-200))]"
                    }`}
                  >
                    {isSelected ? "✓" : ""}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        <div className="mt-6 flex items-center justify-between gap-3">
          <button
            disabled={current === 0}
            onClick={() => setCurrent((c) => c - 1)}
            className="rw-btn-pill rw-btn-ghost disabled:opacity-40"
            data-testid={TID.quizPrev}
          >
            <ChevronLeft className="h-4 w-4" /> Previous
          </button>
          {current < questions.length - 1 ? (
            <button
              onClick={() => setCurrent((c) => c + 1)}
              className="rw-btn-pill rw-btn-primary"
              data-testid={TID.quizNext}
            >
              Next <ChevronRight className="h-4 w-4" />
            </button>
          ) : (
            <button onClick={submit} className="rw-btn-pill rw-btn-primary" data-testid={TID.quizSubmit}>
              Submit
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
