export default function DashboardLoading() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Loading">
      <div className="space-y-2">
        <div className="h-7 w-40 animate-pulse rounded-lg bg-[rgba(255,255,255,0.06)]" />
        <div className="h-4 w-80 max-w-full animate-pulse rounded bg-[rgba(255,255,255,0.05)]" />
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
        {[0, 1, 2, 3, 4].map((i) => (
          <div key={i} className="card-ring h-[120px] animate-pulse" />
        ))}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="card-ring h-[220px] animate-pulse lg:col-span-1" />
        <div className="card-ring h-[220px] animate-pulse lg:col-span-2" />
      </div>

      <div className="card-ring h-[140px] animate-pulse" />
    </div>
  );
}
