/**
 * GitHub Export Modal — stub (feature not available in Mini App)
 */

import {
	Dialog,
	DialogContent,
	DialogHeader,
	DialogTitle,
} from '@/components/ui/dialog';

interface GitHubExportModalProps {
	isOpen: boolean;
	onClose: () => void;
	onExport: () => void;
	isExporting: boolean;
	exportProgress?: string;
	exportResult?: any;
	onRetry: () => void;
	existingGithubUrl?: string | null;
	agentId?: string;
	appTitle?: string;
}

export function GitHubExportModal({ isOpen, onClose, appTitle }: GitHubExportModalProps) {
	return (
		<Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
			<DialogContent className="sm:max-w-md">
				<DialogHeader>
					<DialogTitle>Export to GitHub</DialogTitle>
				</DialogHeader>
				<p className="text-sm text-muted-foreground py-4">
					GitHub export is not available in the Mini App. Please use the web version.
				</p>
			</DialogContent>
		</Dialog>
	);
}
