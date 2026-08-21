export function MaintenanceOverlay() {
  return (
    <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-kumo-base">
      <div className="text-center space-y-4 px-6">
        <div className="text-6xl">🔧</div>
        <h1 className="text-2xl font-bold text-kumo-default">
          Bot Under Maintenance
        </h1>
        <p className="text-kumo-subtle max-w-md">
          The bot is currently being updated. Please try again later.
        </p>
      </div>
    </div>
  );
}
