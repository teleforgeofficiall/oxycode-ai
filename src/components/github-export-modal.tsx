import { useState } from 'react';
import {
	AlertDialog,
	AlertDialogAction,
	AlertDialogCancel,
	AlertDialogContent,
	AlertDialogDescription,
	AlertDialogFooter,
	AlertDialogHeader,
	AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { cn } from '@cloudflare/kumo';
import { CheckCircle, ArrowSquareOut, ArrowClockwise, Spinner } from '@phosphor-icons/react';

interface GitHubExportModalProps {
	isOpen: boolean;
	onClose: () => void;
	onExport: (options: { repoName?: string; isPrivate?: boolean }) => Promise<void>;
	isExporting: boolean;
	exportProgress?: { phase: string; message?: string };
	exportResult?: { url?: string; repoUrl?: string; error?: string } | null;
	onRetry: () => void;
	existingGithubUrl?: string | null;
	agentId?: string;
	appTitle?: string;
}

export function GitHubExportModal({
	isOpen,
	onClose,
	onExport,
	isExporting,
	exportProgress,
	exportResult,
	onRetry,
	existingGithubUrl,
	appTitle,
}: GitHubExportModalProps) {
	const [repoName, setRepoName] = useState(appTitle?.toLowerCase().replace(/\s+/g, '-') || '');
	const [isPrivate, setIsPrivate] = useState(false);

	const handleExport = async () => {
		await onExport({ repoName: repoName || undefined, isPrivate });
	};

	const resultUrl = exportResult?.repoUrl || exportResult?.url;
	const hasError = exportResult?.error;

	return (
		<AlertDialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
			<AlertDialogContent className="sm:max-w-[480px]">
				<AlertDialogHeader>
					<AlertDialogTitle>Export to GitHub</AlertDialogTitle>
					<AlertDialogDescription>
						{existingGithubUrl
							? 'Your app is already exported. You can re-export to update it.'
							: 'Push this app to a new GitHub repository.'}
					</AlertDialogDescription>
				</AlertDialogHeader>

				{isExporting && exportProgress && (
					<div className="flex items-center gap-3 py-4">
						<Spinner className="size-5 text-kumo-brand animate-spin" weight="bold" />
						<div>
							<p className="text-sm font-medium text-kumo-default">{exportProgress.phase}</p>
							{exportProgress.message && (
								<p className="text-xs text-kumo-subtle mt-0.5">{exportProgress.message}</p>
							)}
						</div>
					</div>
				)}

				{hasError && (
					<div className="py-3">
						<p className="text-sm text-red-400">{exportResult!.error}</p>
					</div>
				)}

				{resultUrl && !hasError && (
					<div className="flex items-center gap-3 py-3">
						<CheckCircle className="size-5 text-green-400" weight="fill" />
						<a
							href={resultUrl}
							target="_blank"
							rel="noopener noreferrer"
							className="flex items-center gap-1.5 text-sm text-kumo-brand hover:underline"
						>
							Open repository <ArrowSquareOut className="size-3.5" />
						</a>
					</div>
				)}

				{!isExporting && !resultUrl && !hasError && (
					<div className="space-y-3 py-2">
						<div>
							<label className="text-xs text-kumo-subtle mb-1 block">Repository name</label>
							<input
								type="text"
								value={repoName}
								onChange={(e) => setRepoName(e.target.value)}
								placeholder={appTitle?.toLowerCase().replace(/\s+/g, '-') || 'my-app'}
								className="w-full rounded-lg border border-kumo-line bg-bg-3/50 px-3 py-2 text-sm text-kumo-default placeholder:text-kumo-subtle focus:outline-none focus:ring-2 focus:ring-brand-emphasis/50"
							/>
						</div>
						<label className="flex items-center gap-2 text-sm text-kumo-subtle cursor-pointer">
							<input
								type="checkbox"
								checked={isPrivate}
								onChange={(e) => setIsPrivate(e.target.checked)}
								className="rounded"
							/>
							Make repository private
						</label>
					</div>
				)}

				<AlertDialogFooter>
					{hasError ? (
						<>
							<AlertDialogCancel onClick={onClose}>Cancel</AlertDialogCancel>
							<AlertDialogAction onClick={onRetry} className="bg-kumo-elevated hover:bg-kumo-elevated/80">
								<ArrowClockwise className="size-4 mr-1.5" /> Retry
							</AlertDialogAction>
						</>
					) : resultUrl ? (
						<AlertDialogAction onClick={onClose} className="bg-kumo-elevated hover:bg-kumo-elevated/80">
							Done
						</AlertDialogAction>
					) : (
						<>
							<AlertDialogCancel disabled={isExporting}>Cancel</AlertDialogCancel>
							<AlertDialogAction
								onClick={handleExport}
								disabled={isExporting}
								className="bg-kumo-brand hover:bg-kumo-brand/90 text-white"
							>
								{isExporting ? <Spinner className="size-4 mr-1.5 animate-spin" weight="bold" /> : null}
								{isExporting ? 'Exporting...' : 'Export'}
							</AlertDialogAction>
						</>
					)}
				</AlertDialogFooter>
			</AlertDialogContent>
		</AlertDialog>
	);
}
