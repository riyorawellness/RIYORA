import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import {
  ChevronLeft,
  Download,
  FileText,
  Loader2,
  Music,
  Video,
} from "lucide-react";

import api, { formatApiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { TID } from "@/constants/testIds";

/**
 * Real module player. Fetches the module + program from the API and
 * renders the actual admin-uploaded media (video / audio / pdf).
 *
 * Anti-piracy: a watermark showing the user's full name + membership id
 * overlays every content type. Download is disabled on <video>/<audio>
 * via `controlsList="nodownload"` and blocked from the right-click menu.
 */
export default function ModulePlayer() {
  const { id: programId, moduleId } = useParams();
  const nav = useNavigate();
  const { user } = useAuth();

  const [state, setState] = useState({ loading: true, program: null, module: null, error: null });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [{ data: program }, { data: module }] = await Promise.all([
          api.get(`/programs/${programId}`),
          api.get(`/modules/${moduleId}`),
        ]);
        if (cancelled) return;
        if (module.program_id !== programId) {
          setState({ loading: false, program, module: null, error: "Module doesn't belong to this program." });
          return;
        }
        setState({ loading: false, program, module, error: null });
      } catch (e) {
        if (cancelled) return;
        const msg = formatApiError(e, "Couldn't load this module.");
        setState({ loading: false, program: null, module: null, error: msg });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [programId, moduleId]);

  const goBack = () => {
    if (window.history.length > 1) nav(-1);
    else nav(`/app/programs/${programId}`);
  };

  if (state.loading) {
    return (
      <div className="grid min-h-[60vh] place-items-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (state.error) {
    return (
      <div className="rw-page space-y-4 text-center">
        <button
          onClick={goBack}
          className="mx-auto inline-flex items-center gap-1 text-sm text-muted-foreground"
          data-testid={TID.playerBack}
        >
          <ChevronLeft className="h-4 w-4" /> Back
        </button>
        <p className="rw-serif text-2xl text-red-800">{state.error}</p>
        <p className="text-sm text-muted-foreground">
          If this looks wrong, refresh the page or contact support.
        </p>
      </div>
    );
  }

  const { program, module } = state;
  const watermark = user
    ? `${user.full_name || "Learner"} · ${user.membership_id || ""}`
    : "";

  // Prefer video → audio → pdf. Fall back to "no media" state.
  const hasVideo = !!module.video_url;
  const hasAudio = !hasVideo && !!module.audio_url;
  const hasPDF = !hasVideo && !hasAudio && !!module.pdf_url;
  const hasAny = hasVideo || hasAudio || hasPDF || module.assignment;

  const commonHeader = (
    <div className="flex items-center justify-between px-5 pt-5">
      <button
        onClick={goBack}
        className="grid h-10 w-10 place-items-center rounded-full bg-white/15 text-white"
        data-testid={TID.playerBack}
      >
        <ChevronLeft className="h-5 w-5" />
      </button>
      <div className="text-xs text-white/70">
        {hasVideo && "Streaming · No download"}
        {hasAudio && "Audio · No download"}
        {hasPDF && "PDF · View only"}
        {!hasVideo && !hasAudio && !hasPDF && "Module content"}
      </div>
      <div className="h-10 w-10" />
    </div>
  );

  return (
    <div className="min-h-screen bg-neutral-950 text-white" data-testid="module-player">
      {commonHeader}

      <div className="mx-5 mt-5 space-y-6">
        <div>
          <p className="text-[11px] uppercase tracking-[0.3em] text-white/60">
            Module {module.module_number} · {program.name}
          </p>
          <h1 className="mt-1 rw-serif text-3xl">{module.name}</h1>
          {module.description && (
            <p className="mt-2 text-sm text-white/70">{module.description}</p>
          )}
        </div>

        {hasVideo && (
          <MediaBox watermark={watermark}>
            <video
              key={module.video_url}
              controls
              controlsList="nodownload noplaybackrate"
              disablePictureInPicture
              onContextMenu={(e) => e.preventDefault()}
              className="h-full w-full bg-black"
              data-testid="module-video"
              src={module.video_url}
            >
              Your browser doesn't support HTML5 video.
            </video>
          </MediaBox>
        )}

        {hasAudio && (
          <AudioBox module={module} watermark={watermark} />
        )}

        {hasPDF && (
          <div className="rounded-2xl bg-white">
            <div className="relative">
              <div className="pointer-events-none absolute inset-0 grid place-items-center opacity-10">
                <span className="rotate-[-20deg] rw-serif text-3xl text-neutral-900">
                  {watermark}
                </span>
              </div>
              {/* Google-viewer-style inline iframe. Watermark sits behind. */}
              <iframe
                title={module.name}
                src={`${module.pdf_url}#toolbar=0&navpanes=0`}
                className="h-[75vh] w-full rounded-2xl"
                data-testid="module-pdf"
              />
            </div>
            <p className="p-3 text-center text-[11px] text-neutral-500">
              View only · downloads and screenshots disabled
            </p>
          </div>
        )}

        {!hasAny && (
          <div className="rounded-2xl border border-dashed border-white/20 bg-white/5 p-8 text-center text-white/70">
            <p className="rw-serif text-xl">No media attached yet</p>
            <p className="mt-1 text-sm">
              The admin hasn't uploaded audio, video, or a PDF for this module.
              Please check back soon.
            </p>
          </div>
        )}

        {module.assignment && (
          <div className="rounded-2xl bg-white/5 p-5">
            <div className="mb-2 flex items-center gap-2 text-[11px] uppercase tracking-[0.24em] text-white/60">
              <FileText className="h-3.5 w-3.5" /> Assignment
            </div>
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-white/90">
              {module.assignment}
            </p>
          </div>
        )}
      </div>

      <div className="h-16" />
    </div>
  );
}

function MediaBox({ watermark, children }) {
  return (
    <div className="relative overflow-hidden rounded-2xl bg-black">
      {children}
      <div className="pointer-events-none absolute inset-0 flex flex-col justify-between p-3 text-[10px] font-medium text-white/40">
        <span>{watermark}</span>
        <span className="self-end">{watermark}</span>
      </div>
    </div>
  );
}

function AudioBox({ module, watermark }) {
  const audioRef = useRef(null);
  return (
    <div className="rounded-2xl bg-gradient-to-br from-indigo-900 to-black p-5">
      <div className="mb-3 flex items-center gap-2 text-[11px] uppercase tracking-[0.24em] text-white/60">
        <Music className="h-3.5 w-3.5" /> Audio
      </div>
      <div className="relative">
        <audio
          ref={audioRef}
          src={module.audio_url}
          controls
          controlsList="nodownload noplaybackrate"
          onContextMenu={(e) => e.preventDefault()}
          className="w-full"
          data-testid="module-audio"
        >
          Your browser doesn't support HTML5 audio.
        </audio>
      </div>
      <p className="mt-3 text-[10px] text-white/40">{watermark}</p>
    </div>
  );
}
