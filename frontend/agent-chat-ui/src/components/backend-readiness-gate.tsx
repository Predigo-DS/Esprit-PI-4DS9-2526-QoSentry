"use client";

import React from "react";
import { AlertTriangle, CheckCircle2, LoaderCircle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useBackendReadiness } from "@/hooks/useBackendReadiness";

function StatusLine(props: {
  label: string;
  ready: boolean;
  error?: string;
}) {
  return (
    <div className="rounded-lg border bg-slate-50 px-3 py-2">
      <div className="flex items-center justify-between gap-4">
        <span className="text-sm font-medium text-slate-700">{props.label}</span>
        {props.ready ? (
          <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-700">
            <CheckCircle2 className="size-3.5" />
            Ready
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 text-xs font-medium text-amber-700">
            <LoaderCircle className="size-3.5 animate-spin" />
            Waiting
          </span>
        )}
      </div>
      {!!props.error && (
        <p className="mt-1 text-xs text-rose-700">{props.error}</p>
      )}
    </div>
  );
}

export function BackendReadinessGate({
  children,
}: {
  children: React.ReactNode;
}) {
  const readiness = useBackendReadiness();

  if (readiness.isChecking) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 p-6">
        <div className="w-full max-w-lg rounded-2xl border bg-white p-6 shadow-sm">
          <div className="mb-4 flex items-center gap-2 text-slate-900">
            <LoaderCircle className="size-5 animate-spin" />
            <h1 className="text-lg font-semibold">Preparing services</h1>
          </div>
          <p className="mb-4 text-sm text-slate-600">
            Waiting for Agent and RAG services to become fully operational.
          </p>
          <div className="space-y-2">
            <StatusLine
              label="Agent model service"
              ready={readiness.agentReady}
              error={readiness.agentError}
            />
            <StatusLine
              label="RAG retrieval service"
              ready={readiness.ragReady}
              error={readiness.ragError}
            />
          </div>
        </div>
      </div>
    );
  }

  return (
    <>
      {readiness.isDegraded && (
        <div className="sticky top-0 z-50 border-b border-amber-200 bg-amber-50 px-4 py-3">
          <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center justify-between gap-3">
            <div className="flex items-start gap-2 text-amber-900">
              <AlertTriangle className="mt-0.5 size-4" />
              <div>
                <p className="text-sm font-medium">Running in degraded mode</p>
                <p className="text-xs text-amber-800">
                  Some services are still unavailable. You can continue, or retry readiness checks.
                </p>
              </div>
            </div>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={readiness.retry}
              className="border-amber-300 bg-white text-amber-900 hover:bg-amber-100"
            >
              <RefreshCw className="size-4" />
              Retry
            </Button>
          </div>
        </div>
      )}
      {children}
    </>
  );
}