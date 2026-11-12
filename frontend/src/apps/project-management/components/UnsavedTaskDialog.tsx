import {AlertDialog,AlertDialogContent,AlertDialogHeader,AlertDialogTitle,AlertDialogDescription,AlertDialogFooter,AlertDialogCancel,AlertDialogAction} from "@/components/ui/alert-dialog";

export default function UnsavedTaskDialog({onDiscard,onKeep}:{onDiscard:(()=>void)|null;onKeep:()=>void}){
 return <AlertDialog open={!!onDiscard} onOpenChange={open=>{if(!open)onKeep();}}><AlertDialogContent className="z-[91]" overlayClassName="z-[90]">
  <AlertDialogHeader><AlertDialogTitle>Keep your unsaved task work?</AlertDialogTitle><AlertDialogDescription>Your unsaved fields, failed updates and comment draft will be discarded if you leave. Changes already saved will stay saved.</AlertDialogDescription></AlertDialogHeader>
  <AlertDialogFooter><AlertDialogCancel onClick={onKeep}>Keep editing</AlertDialogCancel><AlertDialogAction onClick={()=>onDiscard?.()}>Discard changes and leave</AlertDialogAction></AlertDialogFooter>
 </AlertDialogContent></AlertDialog>;
}
