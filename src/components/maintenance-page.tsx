import { WrenchIcon } from '@phosphor-icons/react';

export function MaintenancePage() {
  return (
    <div className="flex flex-col items-center justify-center h-full px-6">
      <div className="text-center space-y-5 max-w-md">
        <div className="flex justify-center">
          <div className="size-20 rounded-2xl bg-bg-3 flex items-center justify-center">
            <WrenchIcon className="size-10 text-kumo-brand" weight="duotone" />
          </div>
        </div>
        <div className="space-y-2">
          <h1 className="text-2xl font-bold text-kumo-default">
            Under Maintenance
          </h1>
          <p className="text-kumo-subtle leading-relaxed">
            OXYCODE AI is currently being updated. We'll be back soon!
          </p>
        </div>
        <div className="pt-2">
          <p className="text-xs text-kumo-subtle/60">
            Try again in a few minutes.
          </p>
        </div>
      </div>
    </div>
  );
}
