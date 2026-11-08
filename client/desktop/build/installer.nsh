; One explicit, safe uninstall choice for both client and processing-server editions.
; Silent uninstall and in-place upgrades always preserve the environment and data.
!include nsDialogs.nsh
!include LogicLib.nsh

!if "${APP_ID}" == "app.videotool.server"
  !define VT_DATA_NAME "Ultimate Video Tool Server"
!else
  !define VT_DATA_NAME "Video Tool"
!endif

!macro customHeader
!ifdef BUILD_UNINSTALLER
Var VTDialog
Var VTKeep
Var VTAll
Var VTRemoveAll
Var VTDataRoot

Function un.VTChoices
  ${If} ${Silent}
    Abort
  ${EndIf}
  ${If} ${isUpdated}
    Abort
  ${EndIf}
  !insertmacro MUI_HEADER_TEXT "What should be removed?" "Your videos and settings can stay for next time."
  nsDialogs::Create 1018
  Pop $VTDialog
  ${If} $VTDialog == error
    Abort
  ${EndIf}
  ${NSD_CreateRadioButton} 0 4u 100% 22u "Remove the app, keep my videos and settings (recommended)"
  Pop $VTKeep
  ${NSD_SetState} $VTKeep ${BST_CHECKED}
  ${NSD_CreateLabel} 12u 29u 94% 36u "Reinstalling picks up where you left off, with nothing to download again."
  Pop $0
  ${NSD_CreateRadioButton} 0 78u 100% 22u "Remove everything, including my videos"
  Pop $VTAll
  ${NSD_CreateLabel} 12u 103u 94% 46u "Deletes the app's folder with your videos, settings and downloaded models. Folders you chose yourself, and ComfyUI or Ollama installed separately, are not touched."
  Pop $0
  ${NSD_CreateLabel} 0 162u 100% 30u "Folder: $APPDATA\${VT_DATA_NAME}"
  Pop $0
  nsDialogs::Show
FunctionEnd

Function un.VTChoicesLeave
  StrCpy $VTRemoveAll "0"
  ${NSD_GetState} $VTAll $0
  ${If} $0 == ${BST_CHECKED}
    MessageBox MB_YESNO|MB_ICONEXCLAMATION|MB_DEFBUTTON2 "Delete your videos, settings and models in $APPDATA\${VT_DATA_NAME}?$\r$\n$\r$\nThis can't be undone." IDYES vt_confirmed
    Abort
    vt_confirmed:
    StrCpy $VTRemoveAll "1"
  ${EndIf}
FunctionEnd
!endif
!macroend

!macro customUnInit
  StrCpy $VTRemoveAll "0"
!macroend

!macro customUnWelcomePage
  !insertmacro MUI_UNPAGE_WELCOME
  UninstPage custom un.VTChoices un.VTChoicesLeave
!macroend

!macro customUnInstall
  ; Remove only this edition's login entry, even when the environment is kept.
  !if "${APP_ID}" == "app.videotool.server"
    ${IfNot} ${isUpdated}
      DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "Ultimate Video Tool Server"
      DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "ultimate-video-tool-server"
      DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "electron.app.Electron"
    ${EndIf}
  !else
    ${IfNot} ${isUpdated}
      DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "Ultimate Video Tool Helper"
    ${EndIf}
  !endif
  ${IfNot} ${Silent}
  ${AndIfNot} ${isUpdated}
  ${AndIf} $VTRemoveAll == "1"
    ; Resolve and constrain the sole recursive-delete target before removing it.
    SetShellVarContext current
    GetFullPathName $VTDataRoot "$APPDATA\${VT_DATA_NAME}"
    ${If} $VTDataRoot == "$APPDATA\${VT_DATA_NAME}"
      RMDir /r "$VTDataRoot"
    ${Else}
      MessageBox MB_OK|MB_ICONEXCLAMATION "The app was removed. Its folder was left in place because it could not be checked safely."
    ${EndIf}
    ${If} $installMode == "all"
      SetShellVarContext all
    ${EndIf}
  ${EndIf}
!macroend
