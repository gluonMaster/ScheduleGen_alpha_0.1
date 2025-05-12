Attribute VB_Name = "Modul1"
Sub CreateSchedulePlanning()
    ' This macro reads data from the "Schedule" sheet and creates a new Excel file
    ' with restructured data according to specifications, then runs a series of command line operations
    
    Dim wbSource As Workbook
    Dim wbTarget As Workbook
    Dim wsSource As Worksheet
    Dim wsTarget As Worksheet
    Dim lastRow As Long
    Dim i As Long
    Dim targetRow As Long
    Dim targetPath As String
    Dim targetFileName As String
    Dim roomValue As String
    Dim buildingValue As String
    Dim buildingFirstLetter As String
    Dim shellObj As Object
    Dim cmdPath As String
    Dim waitOnReturn As Boolean
    Dim windowStyle As Integer
    Dim execStatus As Integer
    Dim lastUsedRow As Long
    Dim blockCount As Long
    Dim blockRange As Range
    
    ' Optimize performance
    Application.ScreenUpdating = False
    Application.Calculation = xlCalculationManual
    Application.EnableEvents = False
    Application.DisplayAlerts = False
    
    ' Set references to source workbook and worksheet
    Set wbSource = ThisWorkbook
    Set wsSource = wbSource.Sheets("Schedule")
    
    ' Determine the last row with data in source worksheet
    lastRow = wsSource.Cells(wsSource.Rows.Count, 1).End(xlUp).Row
    
    ' Define target file path and name
    targetPath = wbSource.Path & "\..\..\xlsx_initial\"
    targetFileName = "newpref.xlsx"
    
    ' Create folder if it doesn't exist
    On Error Resume Next
    MkDir targetPath
    On Error GoTo 0
    
    ' Create a new workbook for the target
    Set wbTarget = Workbooks.Add
    
    ' Rename the first sheet to "Plannung"
    Set wsTarget = wbTarget.Sheets(1)
    wsTarget.Name = "Plannung"
    
    ' 1. Add headers and formatting to the first row
    ' 1a. Add header titles
    wsTarget.Cells(1, 2).Value = "Hauptunterricht"
    wsTarget.Cells(1, 3).Value = "Begleitende Unterricht 1"
    wsTarget.Cells(1, 4).Value = "Begleitende Unterricht 2"
    
    ' 1b. Apply light pink background to header row
    wsTarget.Range("B1:D1").Interior.Color = RGB(255, 230, 230)
    
    ' 1c. Freeze the first row
    wsTarget.Range("A2").Select
    ActiveWindow.FreezePanes = True
    
    ' Initialize target row counter
    targetRow = 2
    
    ' Process each row of data from source
    For i = 2 To lastRow
        ' Get room and building values
        roomValue = CStr(wsSource.Cells(i, 4).Value)
        buildingValue = CStr(wsSource.Cells(i, 5).Value)
        
        ' Extract the first letter of the building name and convert to uppercase
        If Len(buildingValue) > 0 Then
            buildingFirstLetter = UCase(Left(buildingValue, 1))
        Else
            buildingFirstLetter = ""
        End If
        
        ' Transfer data according to the new structure
        
        ' 1st row of section: Subject
        wsTarget.Cells(targetRow, 2).Value = wsSource.Cells(i, 1).Value
        
        ' 2nd row of section: Group
        wsTarget.Cells(targetRow + 1, 2).Value = wsSource.Cells(i, 2).Value
        
        ' 3rd row of section: Teacher
        wsTarget.Cells(targetRow + 2, 2).Value = wsSource.Cells(i, 3).Value
        
        ' 4th row of section: Room - with building first letter prefix
        ' Format as text to preserve format like "2.09"
        wsTarget.Cells(targetRow + 3, 2).NumberFormat = "@"
        wsTarget.Cells(targetRow + 3, 2).Value = buildingFirstLetter & roomValue
        
        ' 8th row of section: Building
        wsTarget.Cells(targetRow + 7, 2).Value = buildingValue
        
        ' 9th row of section: Duration
        wsTarget.Cells(targetRow + 8, 2).Value = wsSource.Cells(i, 9).Value
        
        ' 10th row of section: Day of week
        wsTarget.Cells(targetRow + 9, 2).Value = wsSource.Cells(i, 6).Value
        
        ' 11th row of section: Start time
        wsTarget.Cells(targetRow + 10, 2).Value = wsSource.Cells(i, 7).Value
        
        ' Move to the next section (increment by 14 rows)
        targetRow = targetRow + 14
    Next i
    
    ' Get the last used row for formatting
    lastUsedRow = wsTarget.Cells(wsTarget.Rows.Count, 2).End(xlUp).Row
    
    ' 2. Add row labels to column A
    ' 2a. Create array of labels
    Dim labels As Variant
    labels = Array("Unterricht Name", "Gruppe", "Lehrer", "Kabinett", _
                  "Kabinett alter. 1", "Kabinett alter. 2", "Kabinett alter. 3", _
                  "Gebaude", "Dauer (min)", "Tag", "Seit (Zeit)", "Bis (Zeit)", _
                  "Pause vorher (min)", "Pause danach (min)")
    
    ' Calculate number of blocks needed
    blockCount = WorksheetFunction.Ceiling((lastUsedRow - 1) / 14, 1)
    
    ' Add labels to column A for each block
    For i = 0 To blockCount - 1
        For j = 0 To 13
            wsTarget.Cells(2 + i * 14 + j, 1).Value = labels(j)
        Next j
    Next i
    
    ' 2c. Apply light blue background to column A
    wsTarget.Range("A2:A" & (blockCount * 14 + 1)).Interior.Color = RGB(220, 230, 255)
    
    ' 3. Add borders around blocks
    For i = 0 To blockCount - 1
        ' Set the block range
        Set blockRange = wsTarget.Range("A" & (2 + i * 14) & ":D" & (15 + i * 14))
        
        ' Apply thick outer border
        With blockRange.Borders(xlEdgeLeft)
            .LineStyle = xlContinuous
            .Weight = xlThick
        End With
        With blockRange.Borders(xlEdgeRight)
            .LineStyle = xlContinuous
            .Weight = xlThick
        End With
        With blockRange.Borders(xlEdgeTop)
            .LineStyle = xlContinuous
            .Weight = xlThick
        End With
        With blockRange.Borders(xlEdgeBottom)
            .LineStyle = xlContinuous
            .Weight = xlThick
        End With
        
        ' Apply thin inner borders
        With blockRange.Borders(xlInsideHorizontal)
            .LineStyle = xlContinuous
            .Weight = xlThin
        End With
        With blockRange.Borders(xlInsideVertical)
            .LineStyle = xlContinuous
            .Weight = xlThin
        End With
    Next i
    
    ' Autofit column A to display all labels properly
    wsTarget.Columns("A:A").AutoFit
    wsTarget.Columns("B:B").AutoFit
    wsTarget.Columns("C:C").AutoFit
    wsTarget.Columns("D:D").AutoFit
    
    ' Save the target workbook
    On Error Resume Next
    wbTarget.SaveAs targetPath & targetFileName, FileFormat:=xlOpenXMLWorkbook
    
    If Err.Number <> 0 Then
        MsgBox "Error saving file to " & targetPath & targetFileName & vbCrLf & _
               "Error: " & Err.Description, vbExclamation, "Save Error"
        
        ' Restore application settings
        Application.ScreenUpdating = True
        Application.Calculation = xlCalculationAutomatic
        Application.EnableEvents = True
        Application.DisplayAlerts = True
        Exit Sub
    Else
        MsgBox "File successfully created at " & targetPath & targetFileName, vbInformation, "Success"
    End If
    On Error GoTo 0
    
    ' Close the target workbook
    wbTarget.Close SaveChanges:=False
    
'    ' Run command line operations
'    Set shellObj = CreateObject("WScript.Shell")
'    waitOnReturn = True  ' Wait for each command to complete before proceeding
'    windowStyle = 1      ' 1 = normal window
'    
'    ' Display status message
'    Application.StatusBar = "Running command line operations. Please wait..."
'    
'    ' First command: Navigate to the script directory
'    cmdPath = "cmd.exe /c cd /d c:\Konst\2025\Kolibri\Alla\Schedule\SchedGen_PreRelease\ && "
'    
'    ' Second command: Run Python script
'    cmdPath = cmdPath & "python main_sch.py xlsx_initial/newpref.xlsx --time-limit 300 --verbose --time-interval 5 && "
'    
'    ' Third command: Navigate to gear_xls
'    cmdPath = cmdPath & "cd gear_xls && "
'    
'    ' Fourth command: Run the second Python script
'    cmdPath = cmdPath & "python main.py"
'    
'    ' Execute all commands in sequence
'    execStatus = shellObj.Run(cmdPath, windowStyle, waitOnReturn)
'    
'    ' Report status
'    If execStatus = 0 Then
'        MsgBox "All command line operations completed successfully.", vbInformation, "Command Line Success"
'    Else
'        MsgBox "Command line operations completed with exit code: " & execStatus, vbExclamation, "Command Line Execution"
'    End If
    
    ' Clear status bar
    Application.StatusBar = False
    
    ' Restore application settings
    Application.ScreenUpdating = True
    Application.Calculation = xlCalculationAutomatic
    Application.EnableEvents = True
    Application.DisplayAlerts = True
    
    ' Clean up
    Set wsTarget = Nothing
    Set wsSource = Nothing
    Set wbTarget = Nothing
    Set wbSource = Nothing
'    Set shellObj = Nothing
End Sub



