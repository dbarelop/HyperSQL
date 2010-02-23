#!/usr/bin/python

# see main function at bottom of file

"""
    $Id$
    Version 1.0 written by Randy Phillips September 2001
    Copyright 2001 El Paso Energy, Inc.  All Rights Reserved

    Version 1.1+ written by Itzchak Rehberg
    Copyright 2010 Itzchak Rehberg & IzzySoft

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, write to the Free Software
    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

    Author contact information:
       randy-san@users.sourceforge.net
       izzysoft AT qumran DOT org
"""

# first import standard modules we use
import os, sys, string, time, ConfigParser, fileinput
from shutil import copy2

# now import our own modules
sys.path.insert(0,os.path.split(sys.argv[0])[0] + os.sep + 'lib')
from hypercore import *
from hyperjdoc import *
from hypercode import *


def FindFilesAndBuildFileList(dir, fileInfoList, meta_info):
    """
    Recursively scans the source directory specified (1st param) for
    relevant files according to the file extensions configured in meta_info
    (3rd param), while excluding RCS directories (such as 'RCS', 'CVS', and
    '.svn'). Information for matching files is stored in fileInfoList (2nd param).
    """

    # get a list of this directory's contents
    # these items are relative and not absolute
    names=os.listdir(dir)

    # iterate through the file list
    for i in names: 

      if i in meta_info.rcsnames: # do not look in RCS/CVS/SVN/... special dirs
	    continue

      # convert from relative to absolute addressing
      # to allow recursive calls
      f1=os.path.join(dir, i)

      # if this item is also a directory, recurse it too
      if os.path.isdir(f1):
        FindFilesAndBuildFileList(f1, fileInfoList, meta_info)
	    
      else:  # file found, only add specific file extensions to the list
        fspl = f1.split('.')
        ext  = fspl[len(fspl)-1]
        if ext in meta_info.sql_file_exts:
          temp = FileInfo()
          temp.fileName = f1
          temp.fileType = "sql"
          if temp.uniqueNumber == 0:
            temp.uniqueNumber = meta_info.NextIndex()
          fileInfoList.append(temp)
        if ext in meta_info.cpp_file_exts:
          temp = FileInfo()
          temp.fileName = f1
          temp.fileType = "cpp"
          if temp.uniqueNumber == 0:
            temp.uniqueNumber = meta_info.NextIndex()
          fileInfoList.append(temp)

def ScanFilesForViewsAndPackages(meta_info):
    """
    Scans files from meta_info.fileInfoList for views and packages and collects
    some metadata about them (name, file, lineno). When encountering a package
    spec, it also scans for its functions and procedures.
    It simply searches the source file for keywords. With each object info,
    file name and line number are stored (and can be used to identify parent
    and children) - for functions and procedures contained in packages, a link
    to their parent is stored along.
    """

    fileInfoList = meta_info.fileInfoList

    # first, find views in files
    dot_count = 1
    for file_info in fileInfoList:

        # skip all non-sql files
        if file_info.fileType != "sql":
            continue
        
        # print a . every file
        sys.stdout.write(".")
        sys.stdout.flush()
        if (dot_count % 60) == 0: # carriage return every 60 dots
            print
            sys.stdout.flush()

        dot_count += 1
        infile = open(file_info.fileName, "r")
        fileLines = infile.readlines()
        infile.close()

        # scan this file for possible JavaDoc style comments
        jdoc = ScanJavaDoc(fileLines)

        # if we find a package definition, this flag tells us to also look for
        # functions and procedures.  If we don't find a package definition, there
        # is no reason to look for them
        package_count = -1

        for lineNumber in range(len(fileLines)):

            token_list = fileLines[lineNumber].split()

            # ignore very short lines
            if len(token_list) < 2:
                continue

            # ignore lines that begin with comments
            if token_list[0][:2] == "--" or token_list[0][:2] == "//" or token_list[0][:2] == "##":
                continue

            # find views.  Loop through looking for the different styles of view definition
            if metaInfo.indexPage['view'] != '':
                for token_index in range(len(token_list)):
                    # look for CREATE VIEW, REPLACE VIEW, FORCE VIEW, making sure enough tokens exist
                    if len(token_list) > token_index+1 \
                    and token_list[token_index+1].upper() == "VIEW" \
                    and (token_list[token_index].upper() == "CREATE" \
                        or token_list[token_index].upper() == "REPLACE" \
                        or token_list[token_index].upper() == "FORCE"):
                        view_info = ViewInfo()
                        view_info.parent = file_info
                        view_info.viewName = token_list[token_index+2]
                        view_info.lineNumber = lineNumber
                        for j in range(len(jdoc)):
                          ln = jdoc[j].lineNumber - lineNumber
                          if (CaseInsensitiveComparison(view_info.viewName,jdoc[j].name)==0 and jdoc[j].objectType=='view') or (ln>0 and ln<metaInfo.blindOffset) or (ln<0 and ln>-1*metaInfo.blindOffset):
                            view_info.javadoc = jdoc[j]
                        file_info.viewInfoList.append(view_info)

            # find package definitions - set flag if found
            # look for PACKAGE BODY x, making sure enough tokens exist
            for token_index in range(len(token_list)):
                if len(token_list) > token_index+2 \
                and token_list[token_index].upper() == "PACKAGE" \
                and token_list[token_index+1].upper() == "BODY":
                    package_info = PackageInfo()
                    package_info.parent = file_info
                    package_info.packageName = token_list[token_index+2]
                    package_info.lineNumber = lineNumber
                    for j in range(len(jdoc)):
                      ln = jdoc[j].lineNumber - lineNumber
                      if (CaseInsensitiveComparison(package_info.packageName,jdoc[j].name)==0 and jdoc[j].objectType=='pkg') or (ln>0 and ln<metaInfo.blindOffset) or (ln<0 and ln>-1*metaInfo.blindOffset):
                        package_info.javadoc = jdoc[j]
                    file_info.packageInfoList.append(package_info) # permanent storage
                    package_count += 1 # use this flag below
		    
            # if a package definition was found, look for functions and procedures
            if package_count != -1:
                # first find functions
                if len(token_list) > 1 and token_list[0].upper() == "FUNCTION":
                    function_name = token_list[1].split('(')[0] # some are "name(" and some are "name ("
                    function_info = FunctionInfo()
                    function_info.parent = file_info.packageInfoList[package_count]
                    function_info.functionName = function_name
                    function_info.lineNumber = lineNumber
                    for j in range(len(jdoc)):
                      ln = jdoc[j].lineNumber - lineNumber
                      if (CaseInsensitiveComparison(function_name,jdoc[j].name)==0 and jdoc[j].objectType=='function') or (ln>0 and ln<metaInfo.blindOffset) or (ln<0 and ln>-1*metaInfo.blindOffset):
                        function_info.javadoc = jdoc[j]
                    file_info.packageInfoList[package_count].functionInfoList.append(function_info)
		    
                # now find procedures
                if len(token_list) > 1 and token_list[0] == "PROCEDURE":
                    procedure_name = token_list[1].split('(')[0] # some are "name(" and some are "name ("
                    procedure_info = ProcedureInfo()
                    procedure_info.parent = file_info.packageInfoList[package_count]
                    procedure_info.procedureName = procedure_name
                    procedure_info.lineNumber = lineNumber
                    for j in range(len(jdoc)):
                      ln = jdoc[j].lineNumber - lineNumber
                      if (CaseInsensitiveComparison(procedure_name,jdoc[j].name)==0 and jdoc[j].objectType=='procedure') or (ln>0 and ln<metaInfo.blindOffset) or (ln<0 and ln>-1*metaInfo.blindOffset):
                        procedure_info.javadoc = jdoc[j]
                    file_info.packageInfoList[package_count].procedureInfoList.append(procedure_info)

    # print carriage return after last dot
    print


def ScanFilesForWhereViewsAndPackagesAreUsed(meta_info):
    """
    Scans files collected in meta_info.fileInfoList and checks them line by line
    with meta_info.<object>list for calls to those objects. If it finds any, it
    updates <object>list where_used property accordingly.
    """

    fileInfoList = meta_info.fileInfoList

    outerfileInfoList = []
    for file_info in fileInfoList:
        outerfileInfoList.append(file_info)

    dot_count = 1
    for outer_file_info in outerfileInfoList:
        # print a . every file
        sys.stdout.write(".")
        sys.stdout.flush()
        if (dot_count % 60) == 0: # carriage return every 60 dots
            print
            sys.stdout.flush()
        dot_count += 1

        infile = open(outer_file_info.fileName, "r")
        fileLines = infile.readlines()
        infile.close()

        # if we find a package definition, this flag tells us to also look for
        # functions and procedures.  If we don't find a package definition, there
        # is no reason to look for them
        package_count = -1

        for lineNumber in range(len(fileLines)):

            token_list = fileLines[lineNumber].split()

            # ignore very short lines - commented out, since otherwise some where_useds are not found
            #if len(token_list) < 2:
            #    print 'SKIPPED: ' + fileLines[lineNumber]
            #    continue

            # ignore lines that begin with comments
            if len(token_list) > 0:
                if token_list[0][:2] == "--" or token_list[0][:2] == "//" or token_list[0][:2] == "##":
                    continue

            # usage only, no creates, replace, force views packages functions or procedures
            usage_flag = 1
            for token_index in range(len(token_list)):

                # look for CREATE VIEW, REPLACE VIEW, FORCE VIEW, making sure enough tokens exist
                if metaInfo.indexPage['view'] != '' and len(token_list) > token_index+1 \
                and token_list[token_index+1].upper() == "VIEW" \
                and (token_list[token_index].upper() == "CREATE" \
                    or token_list[token_index].upper() == "REPLACE" \
                    or token_list[token_index].upper() == "FORCE"):
                    # we are creating, forcing, or replacing - not using.  Set flag to 0
                    usage_flag = 0

                # look for PACKAGE BODY x IS, making sure enough tokens exist
                if token_list[token_index].upper() == "PACKAGE" \
                and len(token_list) > token_index+2 \
                and token_list[token_index+1].upper() == "BODY":
                    package_count += 1 # set flag
                    usage_flag = 0

                # if a package definition was found, look for functions and procedures
                if package_count != -1:
                    # first find functions
                    if token_list[0] == "FUNCTION" and len(token_list) > 1:
                        usage_flag = 0
                    # now find procedures
                    if token_list[0] == "PROCEDURE" and len(token_list) > 1:
                        usage_flag = 0

            if usage_flag == 0:
                continue

            # Loop through all previously found views and packages to see if they are used in this line of text
            for inner_file_info in fileInfoList:

                # if this FileInfo instance has views
                if len(inner_file_info.viewInfoList) != 0:
                    for view_info in inner_file_info.viewInfoList:
                        # perform case insensitive find
                        if fileLines[lineNumber].upper().find(view_info.viewName.upper()) != -1:
                            if outer_file_info.fileName not in view_info.whereUsed.keys():
                                view_info.whereUsed[outer_file_info.fileName] = []
                                view_info.whereUsed[outer_file_info.fileName].append((outer_file_info, lineNumber))
                            else:
                                view_info.whereUsed[outer_file_info.fileName].append((outer_file_info, lineNumber))
                            # generate a unique number for use in making where used file if needed
                            if view_info.uniqueNumber == 0:
                                view_info.uniqueNumber = meta_info.NextIndex()


                # if this FileInfo instance has packages
                if len(inner_file_info.packageInfoList) != 0:
                    for package_info in inner_file_info.packageInfoList:

                        # perform case insensitive find, this is "package name"."function or procedure name"
                        if fileLines[lineNumber].upper().find(package_info.packageName.upper() + ".") != -1:

                            if outer_file_info.fileName not in package_info.whereUsed.keys():
                                package_info.whereUsed[outer_file_info.fileName] = []
                                package_info.whereUsed[outer_file_info.fileName].append((outer_file_info, lineNumber))
                            else:
                                package_info.whereUsed[outer_file_info.fileName].append((outer_file_info, lineNumber))
                            # generate a unique number for use in making where used file if needed
                            if package_info.uniqueNumber == 0:
                                package_info.uniqueNumber = meta_info.NextIndex()

                            #look for any of this packages' functions
                            for function_info in package_info.functionInfoList:
                                # perform case insensitive find
                                if fileLines[lineNumber].upper().find(package_info.packageName.upper() + "." \
                                  + function_info.functionName.upper()) != -1:
                                    if outer_file_info.fileName not in function_info.whereUsed.keys():
                                        function_info.whereUsed[outer_file_info.fileName] = []
                                        function_info.whereUsed[outer_file_info.fileName].append((outer_file_info, lineNumber))
                                    else:
                                        function_info.whereUsed[outer_file_info.fileName].append((outer_file_info, lineNumber))
                                    # generate a unique number for use in making where used file if needed
                                    if function_info.uniqueNumber == 0:
                                        function_info.uniqueNumber = meta_info.NextIndex()
                            #look for any of this packages procedures
                            for procedure_info in package_info.procedureInfoList:
                                # perform case insensitive find
                                if fileLines[lineNumber].upper().find(package_info.packageName.upper() + "." \
                                  + procedure_info.procedureName.upper()) != -1:
                                    if outer_file_info.fileName not in procedure_info.whereUsed.keys():
                                        procedure_info.whereUsed[outer_file_info.fileName] = []
                                        procedure_info.whereUsed[outer_file_info.fileName].append((outer_file_info, lineNumber))
                                    else:
                                        procedure_info.whereUsed[outer_file_info.fileName].append((outer_file_info, lineNumber))
                                    # generate a unique number for use in making where used file if needed
                                    if procedure_info.uniqueNumber == 0:
                                        procedure_info.uniqueNumber = meta_info.NextIndex()

    # print carriage return after last dot
    print

def MakeNavBar(current_page):
    """Generates HTML code for the general navigation links to all the index pages"""
    itemCount = 0
    lineNumber = 1
    s = "<TABLE ID='topbar' WIDTH='98%'><TR>\n"
    s += "  <TD ID='navbar' WIDTH='600px'>\n"
    #for item in ['package','function','procedure','package_full','view','file','filepath','bug','todo']:
    for item in ['package','function','procedure','package_full','view','file','filepath']:
        if metaInfo.indexPage[item] == '':
            continue
        if current_page == item:
            s += '    <B><I>' + metaInfo.indexPageName[item] + '</I></B> &nbsp;&nbsp; \n'
        else:
            s += '    <A href="' + metaInfo.indexPage[item] + '">' + metaInfo.indexPageName[item] + '</A> &nbsp;&nbsp; \n'
        itemCount += 1
        if lineNumber < 2 and float(metaInfo.indexPageCount) / itemCount <= 2:
            s += '    <BR>\n'
            lineNumber += 1
    if current_page == 'Index':
        s += '    <B><I>Main Index</I></B>\n'
    else:
        s += '    <A href="index.html">Main Index</A>\n'
    s += "  </TD><TD CLASS='title'>\n"
    s += '    ' + metaInfo.title_prefix + '\n'
    s += '  </TD>\n'
    s += '</TR></TABLE>\n'
    return s

def MakeHTMLHeader(meta_info, title_name):
    """Generates common HTML header with menu for all pages"""

    #if title_name in ['file', 'filepath', 'view', 'package', ]
    if title_name in metaInfo.indexPageName:
        title_text = metaInfo.indexPageName[title_name]
    else:
        title_text = title_name

    s =  '<html><head>\n'
    s += '  <TITLE>' + metaInfo.title_prefix + ': ' + title_text + '</TITLE>\n'
    s += '  <LINK REL="stylesheet" TYPE="text/css" HREF="' + metaInfo.css_file + '">\n'
    s += '</head><body>\n'
    s += MakeNavBar(title_name)
    s += '<HR CLASS="topend">\n'
    return s

def MakeHTMLFooter(title_name):
    """Generates common HTML footer for all pages"""

    if title_name in metaInfo.indexPageName:
        title_text = metaInfo.indexPageName[title_name]
    else:
        title_text = title_name

    s = "<HR CLASS='bottomstart'>\n"
    s += "<DIV ID='bottombar'>\n"
    s += MakeNavBar(title_name)
    s += "  <DIV ID='generated'>Generated by <A HREF='http://projects.izzysoft.de/trac/hypersql/'>HyperSQL</A> v" + metaInfo.versionString + " at " + time.asctime(time.localtime(time.time())) + "</DIV>";
    s += "</DIV>\n"
    s += "</body></html>"
    return s


def CreateHTMLDirectory(metaInfo):
    """Creates the html directory if needed"""
    splitted = metaInfo.htmlDir.split(os.sep)
    temp = ""
    for path_element in splitted: # loop through path components, making directories as needed
        temp += path_element + os.sep
        if os.access(temp, os.F_OK) == 1:
            continue
        else:
            os.mkdir(temp)


def MakeFileIndexWithPathNames(meta_info):
    """Generate HTML index page for all files, ordered by path names"""

    if metaInfo.indexPage['filepath'] == '':
        return

    print "Creating filename by path index"

    fileInfoList = meta_info.fileInfoList
    html_dir = meta_info.htmlDir
    outfilename = metaInfo.indexPage['filepath']

    filenametuplelist = []
    for file_info in fileInfoList:
        # skip all non-sql files
        if file_info.fileType != "sql":
            continue        
        filenametuplelist.append((file_info.fileName.upper(), file_info))
    filenametuplelist.sort(TupleCompareFirstElements)

    outfile = open(html_dir + outfilename, "w")
    outfile.write(MakeHTMLHeader(meta_info, 'filepath'))
    outfile.write("<H1>Index Of All Files By Path Name</H1>\n")
    outfile.write("<TABLE CLASS='apilist' ALIGN='center'><TR><TD>\n")

    for filenametuple in filenametuplelist:
        file_name = filenametuple[1].fileName
        temp = os.path.split(file_name)[1].replace(".", "_")
        temp += "_" + `filenametuple[1].uniqueNumber` + ".html"
        outfile.write("  <A href=\"" + temp + "\">" + file_name[len(meta_info.topLevelDirectory)+1:])
        outfile.write("</A><BR>\n")

    outfile.write("</TD></TR></TABLE>\n")
    outfile.write(MakeHTMLFooter('filepath'))
    outfile.close()
	

def MakeFileIndexNoPathNames(meta_info):
    """Generate HTML index page for all files, ordered by file names, ignoring the path for ordering"""

    if metaInfo.indexPage['file'] == '':
        return

    print "Creating filename no path index"

    fileInfoList = meta_info.fileInfoList
    html_dir = meta_info.htmlDir
    outfilename = metaInfo.indexPage['file']

    filenametuplelist = []
    for file_info in fileInfoList:
        # skip all non-sql files
        if file_info.fileType != "sql":
            continue
        filenametuplelist.append((os.path.split(file_info.fileName)[1].upper(), file_info))
    filenametuplelist.sort(TupleCompareFirstElements)

    outfile = open(html_dir + outfilename, "w")
    outfile.write(MakeHTMLHeader(meta_info, 'file'))
    outfile.write("<H1>Index Of All Files By File Name</H1>\n")
    outfile.write("<TABLE CLASS='apilist' ALIGN='center'><TR><TD>\n")

    for filenametuple in filenametuplelist:
        file_name = filenametuple[1].fileName
        temp = os.path.split(file_name)[1].replace(".", "_")
        temp += "_" + `filenametuple[1].uniqueNumber` + ".html"
        outfile.write("  <A href=\"" + temp + "\">" + os.path.split(file_name)[1])
        outfile.write("</A><BR>\n")

    outfile.write("</TD></TR></TABLE>\n")
    outfile.write(MakeHTMLFooter('file'))
    outfile.close()
	

def MakeViewIndex(meta_info):
    """Generate HTML index page for all views"""

    if metaInfo.indexPage['view'] == '':
        return

    print "Creating view index"

    fileInfoList = meta_info.fileInfoList
    html_dir = meta_info.htmlDir
    outfilename = metaInfo.indexPage['view']
    top_level_directory = meta_info.topLevelDirectory

    viewtuplelist = []
    for file_info in fileInfoList:
        # skip all non-sql files
        if file_info.fileType != "sql":
            continue        
        for view_info in file_info.viewInfoList:
            viewtuplelist.append((view_info.viewName.upper(), view_info, file_info)) # append as tuple for case insensitive sort

    viewtuplelist.sort(TupleCompareFirstElements)

    outfile = open(html_dir + outfilename, "w")
    outfile.write(MakeHTMLHeader(meta_info, 'view'))
    outfile.write("<H1>Index Of All Views</H1>\n")
    outfile.write("<TABLE CLASS='apilist' ALIGN='center'>\n")
    outfile.write("  <TR><TH>View</TH><TH>Details</TH><TH>Used</TH></TR>\n")

    for view_tuple in viewtuplelist: # list of tuples describing every view
        # file name and line number as an HTML reference
        if metaInfo.includeSource:
            HTMLref = os.path.split(view_tuple[2].fileName)[1].replace(".", "_")
            HTMLref += "_" + `view_tuple[2].uniqueNumber` + ".html"
            HTMLref += "#" + `view_tuple[1].lineNumber`
            outfile.write("  <TR><TD><A href=\"" + HTMLref + "\">" + view_tuple[1].viewName.lower() + "</A></TD>")
        else:
            outfile.write("  <TR><TD>" + view_tuple[1].viewName.lower() + "</TD>")
        outfile.write("<TD>" + view_tuple[1].javadoc.getShortDesc() + "</TD>")

        if len(view_tuple[1].whereUsed.keys()) > 0:
            HTMLwhereusedref = "where_used_" + `view_tuple[1].uniqueNumber` + ".html"
            outfile.write("<TD><A href=\"" + HTMLwhereusedref + "\">where used list</A></TD>")
        else:
            outfile.write("<TD>no use found by HyperSQL</TD>")
        outfile.write("</TR>\n")

    outfile.write("</TABLE>\n")
    outfile.write(MakeHTMLFooter('view'))
    outfile.close()


def MakePackageIndex(meta_info):
    """Generate HTML index page for all packages"""

    if metaInfo.indexPage['package'] == '':
        return

    print "Creating package index"

    fileInfoList = meta_info.fileInfoList
    html_dir = meta_info.htmlDir
    outfilename = metaInfo.indexPage['package']
    top_level_directory = meta_info.topLevelDirectory

    packagetuplelist = []
    for file_info in fileInfoList:
        # skip all non-sql files
        if file_info.fileType != "sql":
            continue        
        for package_info in file_info.packageInfoList:
            packagetuplelist.append((package_info.packageName.upper(), package_info, file_info)) # append as tuple for case insensitive sort

    packagetuplelist.sort(TupleCompareFirstElements)

    outfile = open(html_dir + outfilename, "w")
    outfile.write(MakeHTMLHeader(meta_info, 'package'))
    outfile.write("<H1>Index Of All Packages</H1>\n")
    outfile.write("<TABLE CLASS='apilist' ALIGN='center'>\n")
    outfile.write("  <TR><TH>Package</TH><TH>Details</TH><TH>Used</TH></TR>\n")

    for package_tuple in packagetuplelist: # list of tuples describing every package file name and line number as an HTML reference
        HTMLref = os.path.split(package_tuple[2].fileName)[1].replace(".", "_")
        HTMLref += "_" + `package_tuple[2].uniqueNumber` + ".html"
        if package_tuple[1].javadoc.isDefault():
            HTMLjref = ''
        else:
            HTMLjref = HTMLref + '#' + package_tuple[1].javadoc.name + '_' + `package_tuple[1].uniqueNumber`
        HTMLref += "#" + `package_tuple[1].lineNumber`
        if HTMLjref == '':
            outfile.write("  <TR><TD>" + package_tuple[1].packageName.lower())
            if metaInfo.includeSource:
                outfile.write(" <SUP><A href=\"" + HTMLref + "\">#</SUP></A>")
            outfile.write("</TD>")
        else:
            outfile.write("  <TR><TD><A HREF='" + HTMLjref + "'>" + package_tuple[1].packageName.lower() + "</A>")
            if metaInfo.includeSource:
                outfile.write("<SUP><A href=\"" + HTMLref + "\">#</SUP></A>")
            outfile.write("</TD>")
        outfile.write("<TD>" + package_tuple[1].javadoc.getShortDesc() + "</TD>")
        if len(package_tuple[1].whereUsed.keys()) > 0:
            HTMLwhereusedref = "where_used_" + `package_tuple[1].uniqueNumber` + ".html"
            outfile.write("<TD><A href=\"" + HTMLwhereusedref + "\">where used list</A></TD></TR>\n")
        else:
            outfile.write("<TD>no use found by HyperSQL</TD></TR>\n")

    outfile.write("</TABLE>\n")
    outfile.write(MakeHTMLFooter('package'))
    outfile.close()


def MakeFunctionIndex(meta_info):
    """Generate HTML index page for all functions"""

    if metaInfo.indexPage['function'] == '':
        return

    print "Creating function index"

    fileInfoList = meta_info.fileInfoList
    html_dir = meta_info.htmlDir
    outfilename = metaInfo.indexPage['function']
    top_level_directory = meta_info.topLevelDirectory

    functiontuplelist = []
    for file_info in fileInfoList:
        # skip all non-sql files
        if file_info.fileType != "sql":
            continue        
        for package_info in file_info.packageInfoList:
            for function_info in package_info.functionInfoList:
                functiontuplelist.append((function_info.functionName.upper(), function_info, file_info, package_info)) # append as tuple for case insensitive sort

    functiontuplelist.sort(TupleCompareFirstElements)

    outfile = open(html_dir + outfilename, "w")
    outfile.write(MakeHTMLHeader(meta_info, 'function'))
    outfile.write("<H1>Index Of All Functions</H1>\n")
    outfile.write("<TABLE CLASS='apilist' ALIGN='center'>\n")
    outfile.write("  <TR><TH>Function</TH><TH>from Package</TH><TH>Details</TH><TH>Used</TH></TR>\n")

    for function_tuple in functiontuplelist: # list of tuples describing every function file name and line number as an HTML reference
        # HTML[j]ref links to function Code / [ApiDoc]
        HTMLref = os.path.split(function_tuple[2].fileName)[1].replace(".", "_")
        HTMLref += "_" + `function_tuple[2].uniqueNumber` + ".html"
        if function_tuple[1].javadoc.isDefault():
            HTMLjref = ''
        else:
            HTMLjref = HTMLref + '#' + function_tuple[1].javadoc.name + '_' + `function_tuple[1].uniqueNumber`
        # HTMLp[j]ref links to package Code [ApiDoc]
        if function_tuple[3].javadoc.isDefault():
            HTMLpjref = ''
        else:
            HTMLpjref = HTMLref + '#' + function_tuple[3].packageName.lower() + '_' + `function_tuple[3].uniqueNumber`
        HTMLpref = HTMLref + "#" + `function_tuple[3].lineNumber`
        HTMLref += "#" + `function_tuple[1].lineNumber`
        if HTMLjref == '':
            outfile.write("  <TR><TD>" + function_tuple[1].functionName.lower())
            if metaInfo.includeSource:
                outfile.write(" <SUP><A href=\"" + HTMLref + "\">#</SUP></A>")
            outfile.write("</TD>")
        else:
            outfile.write("  <TR><TD><A HREF='" + HTMLjref + "'>" + function_tuple[1].functionName.lower() + "</A>")
            if metaInfo.includeSource:
                outfile.write(" <SUP><A href=\"" + HTMLref + "\">#</SUP></A>")
            outfile.write("</TD>")
        outfile.write("<TD>")
        if HTMLpjref == '':
            outfile.write(function_tuple[3].packageName.lower())
            if metaInfo.includeSource:
                outfile.write(" <SUP><A HREF='" + HTMLpref + "'>#</A>")
        else:
            outfile.write("<A HREF='" + HTMLpjref + "'>" + function_tuple[3].packageName.lower() + "</A>")
            if metaInfo.includeSource:
                outfile.write(" <SUP><A HREF='" + HTMLpref + "'>#</A>")
        outfile.write("</TD>")
        outfile.write("<TD>" + function_tuple[1].javadoc.getShortDesc() + "</TD>")
        if len(function_tuple[1].whereUsed.keys()) > 0:
            HTMLwhereusedref = "where_used_" + `function_tuple[1].uniqueNumber` + ".html"
            outfile.write("<TD><A href=\"" + HTMLwhereusedref + "\">where used list</A></TD>\n")
        else:
            outfile.write("<TD>no use found by HyperSQL</TD>")
        outfile.write("</TR>\n")

    outfile.write("</TABLE>\n")
    outfile.write(MakeHTMLFooter('function'))
    outfile.close()


def MakeProcedureIndex(meta_info):
    """Generate HTML index page for all procedures"""

    if metaInfo.indexPage['procedure'] == '':
        return

    print "Creating procedure index"

    fileInfoList = meta_info.fileInfoList
    html_dir = meta_info.htmlDir
    outfilename = metaInfo.indexPage['procedure']
    top_level_directory = meta_info.topLevelDirectory

    proceduretuplelist = []
    for file_info in fileInfoList:
        # skip all non-sql files
        if file_info.fileType != "sql":
            continue        
        for package_info in file_info.packageInfoList:
            for procedure_info in package_info.procedureInfoList:
                proceduretuplelist.append((procedure_info.procedureName.upper(), procedure_info, file_info, package_info)) # append as tuple for case insensitive sort

    proceduretuplelist.sort(TupleCompareFirstElements)

    outfile = open(html_dir + outfilename, "w")
    outfile.write(MakeHTMLHeader(meta_info, 'procedure'))
    outfile.write("<H1>Index Of All Procedures</H1>\n")
    outfile.write("<TABLE CLASS='apilist' ALIGN='center'>\n")
    outfile.write("  <TR><TH>Procedure</TH><TH>from Package</TH><TH>Details</TH><TH>Used</TH></TR>\n")

    for procedure_tuple in proceduretuplelist: # list of tuples describing every function
        # file name and line number as an HTML reference
        # HTML[j]ref links to procedure Code [ApiDoc]
        HTMLref = os.path.split(procedure_tuple[2].fileName)[1].replace(".", "_")
        HTMLref += "_" + `procedure_tuple[2].uniqueNumber` + ".html"
        if procedure_tuple[1].javadoc.isDefault():
            HTMLjref = ''
        else:
            HTMLjref = HTMLref + '#' + procedure_tuple[1].javadoc.name + '_' + `procedure_tuple[1].uniqueNumber`
        # HTMLp[j]ref links to package Code [ApiDoc]
        if procedure_tuple[3].javadoc.isDefault():
            HTMLpjref = ''
        else:
            HTMLpjref = HTMLref + '#' + procedure_tuple[3].packageName.lower() + '_' + `procedure_tuple[3].uniqueNumber`
        HTMLpref = HTMLref + "#" + `procedure_tuple[3].lineNumber`
        HTMLref += "#" + `procedure_tuple[1].lineNumber`
        if HTMLjref == '':
            outfile.write("  <TR><TD>" + procedure_tuple[1].procedureName.lower())
            if metaInfo.includeSource:
                outfile.write(" <SUP><A href=\"" + HTMLref + "\">#</SUP></A></TD>")
        else:
            outfile.write("  <TR><TD><A HREF='" + HTMLjref + "'>" + procedure_tuple[1].procedureName.lower() + "</A>")
            if metaInfo.includeSource:
                outfile.write(" <SUP><A href=\"" + HTMLref + "\">#</SUP></A>")
            outfile.write("</TD>")
        outfile.write("<TD>")
        if HTMLpjref == '':
            outfile.write(procedure_tuple[3].packageName.lower())
            if metaInfo.includeSource:
                outfile.write(" <SUP><A HREF='" + HTMLpref + "'>#</A>")
        else:
            outfile.write("<A HREF='" + HTMLpjref + "'>" + procedure_tuple[3].packageName.lower() + "</A>")
            if metaInfo.includeSource:
                outfile.write(" <SUP><A HREF='" + HTMLpref + "'>#</A>")
        outfile.write("</TD>")
        outfile.write("<TD>" + procedure_tuple[1].javadoc.getShortDesc() + "</TD>")
        if len(procedure_tuple[1].whereUsed.keys()) > 0:
            HTMLwhereusedref = "where_used_" + `procedure_tuple[1].uniqueNumber` + ".html"
            outfile.write("<TD><A href=\"" + HTMLwhereusedref + "\">where used list</A></TD>")
        else:
            outfile.write("<TD>no use found by HyperSQL</TD>")
        outfile.write("</TR>\n")

    outfile.write("</TABLE>\n")
    outfile.write(MakeHTMLFooter('procedure'))
    outfile.close()

def MakePackagesWithFuncsAndProcsIndex(meta_info):
    """Generate HTML index page for all packages, including their functions and procedures"""

    if metaInfo.indexPage['package_full'] == '':
        return

    print "Creating 'package with functions and procedures' index"

    fileInfoList = meta_info.fileInfoList
    html_dir = meta_info.htmlDir
    outfilename = metaInfo.indexPage['package_full']
    top_level_directory = meta_info.topLevelDirectory

    packagetuplelist = []
    for file_info in fileInfoList:
        # skip all non-sql files
        if file_info.fileType != "sql":
            continue        
        for package_info in file_info.packageInfoList:
            packagetuplelist.append((package_info.packageName.upper(), package_info, file_info)) # append as tuple for case insensitive sort

    packagetuplelist.sort(TupleCompareFirstElements)

    outfile = open(html_dir + outfilename, "w")
    outfile.write(MakeHTMLHeader(meta_info, 'package_full'))
    outfile.write("<H1>Index Of All Packages, Their Functions And Procedures</H1>\n")

    for package_tuple in packagetuplelist:
        # file name and line number as an HTML reference
        HTMLref = os.path.split(package_tuple[2].fileName)[1].replace(".", "_")
        HTMLref += "_" + `package_tuple[2].uniqueNumber` + ".html"
        if package_tuple[1].javadoc.isDefault():
            HTMLjref = ''
        else:
            HTMLjref = HTMLref + '#' + package_tuple[1].javadoc.name + `package_tuple[1].uniqueNumber`
        HTMLref += "#" + `package_tuple[1].lineNumber`
        outfile.write("<TABLE CLASS='apilist' ALIGN='center' WIDTH='98%'>\n  <TR><TH COLSPAN='3'>" + package_tuple[1].packageName.lower() + "</TH></TR>\n")
        outfile.write("  <TR><TD ALIGN='center' WIDTH='33.33%'>")
        if metaInfo.includeSource:
            outfile.write("<A href=\"" + HTMLref + "\">Code</A>")
        else:
            outfile.write("&nbsp;")
        outfile.write("</TD><TD ALIGN='center' WIDTH='33.34%'>")
        if HTMLjref == '':
            outfile.write("&nbsp;")
        else:
            outfile.write("<A HREF='" + HTMLjref + "'>ApiDoc</A>")
        outfile.write("</TD><TD ALIGN='center' WIDTH='33.33%'>")
        if len(package_tuple[1].whereUsed.keys()) > 0:
            HTMLwhereusedref = "where_used_" + `package_tuple[1].uniqueNumber` + ".html"
            outfile.write("<A href=\"" + HTMLwhereusedref + "\">Where Used</A>")
        else:
            outfile.write("no use found by HyperSQL")
        outfile.write("</TD></TR>\n")

        # functions in this package
        functiontuplelist = []
        for function_info in package_tuple[1].functionInfoList:
            functiontuplelist.append((function_info.functionName.upper(), function_info, package_tuple[2])) # append as tuple for case insensitive sort

        functiontuplelist.sort(TupleCompareFirstElements)
        if len(functiontuplelist) != 0:
            outfile.write("  <TR><TH class='sub' COLSPAN='3'>Functions</TH></TR>\n  <TR><TD COLSPAN='3'>")
            outfile.write("<TABLE ALIGN='center'>\n")
            outfile.write("    <TR><TD ALIGN='center'><B>Function</B></TD><TD ALIGN='center'><B>Details</B></TD><TD ALIGN='center'><B>Used</B></TD></TR>\n")
        for function_tuple in functiontuplelist:
            HTMLref = os.path.split(function_tuple[2].fileName)[1].replace(".", "_")
            HTMLref += "_" + `function_tuple[2].uniqueNumber` + ".html"
            HTMLref += "#" + `function_tuple[1].lineNumber`
            outfile.write("    <TR><TD><A href=\"" + HTMLref + "\">" + function_tuple[1].functionName.lower() + "</A></TD>\n")
            outfile.write("<TD>" + function_tuple[1].javadoc.getShortDesc() + "</TD>")
            outfile.write("        <TD>")
            if len(function_tuple[1].whereUsed.keys()) > 0:
                HTMLwhereusedref = "where_used_" + `function_tuple[1].uniqueNumber` + ".html"
                outfile.write("<A href=\"" + HTMLwhereusedref + "\">where used list</A>")
            else:
                outfile.write("no use found by HyperSQL")
            outfile.write("</TD></TR>\n")
        if len(functiontuplelist) != 0:
            outfile.write("</TABLE></TD></TR>\n")
	    
        # procedures in this package
        proceduretuplelist = []
        for procedure_info in package_tuple[1].procedureInfoList:
            proceduretuplelist.append((procedure_info.procedureName.upper(), procedure_info, package_tuple[2])) # append as tuple for case insensitive sort

        proceduretuplelist.sort(TupleCompareFirstElements)
        if len(proceduretuplelist) != 0:
            outfile.write("  <TR><TH class='sub' COLSPAN='3'>Procedures</TH></TR>\n  <TR><TD COLSPAN='3'>")
            outfile.write("<TABLE ALIGN='center'>\n")
            outfile.write("    <TR><TD ALIGN='center'><B>Procedure</B></TD><TD ALIGN='center'><B>Details</B></TD><TD ALIGN='center'><B>Used</B></TD></TR>\n")
        for procedure_tuple in proceduretuplelist:
            HTMLref = os.path.split(procedure_tuple[2].fileName)[1].replace(".", "_")
            HTMLref += "_" + `procedure_tuple[2].uniqueNumber` + ".html"
            HTMLref += "#" + `procedure_tuple[1].lineNumber`
            outfile.write("    <TR><TD><A href=\"" + HTMLref + "\">" + procedure_tuple[1].procedureName.lower() + "</A></TD>\n")
            outfile.write("<TD>" + procedure_tuple[1].javadoc.getShortDesc() + "</TD>")
            outfile.write("        <TD>")
            if len(procedure_tuple[1].whereUsed.keys()) > 0:
                HTMLwhereusedref = "where_used_" + `procedure_tuple[1].uniqueNumber` + ".html"
                outfile.write("<A href=\"" + HTMLwhereusedref + "\">where used list</A>")
            else:
                outfile.write("no use found by HyperSQL")
            outfile.write("</TD></TR>\n")
        if len(proceduretuplelist) != 0:
            outfile.write("</TABLE></TD></TR>\n")
        outfile.write("</TABLE>\n")

    outfile.write(MakeHTMLFooter('package_full'))
    outfile.close()


def CreateHyperlinkedSourceFilePages(meta_info):
    """
    Generates pages with the complete source code of each file, including link
    targets (A NAME=) for each line. This way we can link directly to the line
    starting the definition of an object, or where it is called (used) from.
    Very basic syntax highlighting is performed here as well.
    """

    fileInfoList = meta_info.fileInfoList
    html_dir = meta_info.htmlDir
    top_level_directory = meta_info.topLevelDirectory

    sqlkeywords = []
    sqltypes    = []
    for line in fileinput.input(os.path.split(sys.argv[0])[0] + os.sep + 'sql.keywords'):
      if line.strip()[0]=='#':
        continue
      sqlkeywords.append(line.strip())
    for line in fileinput.input(os.path.split(sys.argv[0])[0] + os.sep + 'sql.types'):
      if line.strip()[0]=='#':
        continue
      sqltypes.append(line.strip())

    dot_count = 1
    for file_info in fileInfoList:
        # skip all non-sql files
        if file_info.fileType != "sql":
            continue

	# print a . every file
	sys.stdout.write(".")
	sys.stdout.flush()
	if (dot_count % 60) == 0: # carriage return every 60 dots
	    print
	    sys.stdout.flush()
	dot_count += 1

        # read up the source file
        infile = open(file_info.fileName, "r")
        infile_line_list = infile.readlines()
        infile.close()

        # generate a file name for us to write to (+1 for delimiter)
        outfilename = os.path.split(file_info.fileName)[1].replace(".", "_")
        outfilename += "_" + `file_info.uniqueNumber` + ".html"

        outfile = open(html_dir + outfilename, "w")
        outfile.write(MakeHTMLHeader(meta_info, file_info.fileName[len(top_level_directory)+1:]))
        outfile.write("<H1>" + file_info.fileName[len(top_level_directory)+1:] + "</H1>\n")

        # ===[ JAVADOC STARTS HERE ]===
        # Do we have views in this file?
        viewdetails = '\n\n'
        #if len(file_info.viewInfoList) > 0:
            #print 'We have views here'
            # Do we have to introduce JavaDoc here as well?

        # Do we have packages in this file?
        packagedetails = '\n\n'
        if len(file_info.packageInfoList) > 0:
            outfile.write('<H2 CLASS="api">Package Overview</H2>\n')
            outfile.write('<TABLE CLASS="apilist" ALIGN="center">\n')
            for p in range(len(file_info.packageInfoList)):
                jdoc = file_info.packageInfoList[p].javadoc
                outfile.write(' <TR><TH COLSPAN="2">' + file_info.packageInfoList[p].packageName + '</TH></TR>\n')
                outfile.write(' <TR><TD COLSPAN="2">')
                outfile.write( jdoc.getHtml(0) )
                outfile.write('</TD></TR>\n')
                # Check the packages for functions
                if len(file_info.packageInfoList[p].functionInfoList) > 0:
                    packagedetails += '<A NAME="funcs"></A><H2>Functions</H2>\n';
                    outfile.write(' <TR><TH CLASS="sub" COLSPAN="2">Functions</TH></TR>\n')
                    for item in file_info.packageInfoList[p].functionInfoList:
                        if item.javadoc.name != '':
                            iname = '<A HREF="#'+item.javadoc.name+'_'+str(item.uniqueNumber)+'">'+item.javadoc.name+'</A>'
                            idesc = item.javadoc.getShortDesc()
                        else:
                            iname = item.functionName
                            idesc = ''
                        outfile.write(' <TR><TD><DIV STYLE="margin-left:15px;text-indent:-15px;">'+iname)
                        if metaInfo.includeSource:
                            outfile.write(' <SUP><A HREF="#'+str(item.lineNumber)+'">#</A></SUP>')
                        outfile.write(' (')
                        if len(item.javadoc.params) > 0:
                            ph = ''
                            for par in item.javadoc.params:
                                ph += ', '+par.sqltype+' '+par.name
                            outfile.write(ph[2:])
                        outfile.write(')</DIV></TD><TD>'+idesc+'</TD></TR>\n')
                        packagedetails += item.javadoc.getHtml(item.uniqueNumber)
                # Check the packages for procedures
                if len(file_info.packageInfoList[p].procedureInfoList) > 0:
                    packagedetails += '<A NAME="procs"></A><H2>Procedures</H2>\n';
                    outfile.write(' <TR><TH CLASS="sub" COLSPAN="2">Procedures</TH></TR>\n')
                    for item in file_info.packageInfoList[p].procedureInfoList:
                        if item.javadoc.name != '':
                            iname = '<A HREF="#'+item.javadoc.name+'_'+str(item.uniqueNumber)+'">'+item.javadoc.name+'</A>'
                            idesc = item.javadoc.getShortDesc()
                        else:
                            iname = item.procedureName
                            idesc = ''
                        outfile.write(' <TR><TD><DIV STYLE="margin-left:15px;text-indent:-15px;">'+iname)
                        if metaInfo.includeSource:
                            outfile.write(' <SUP><A HREF="#'+str(item.lineNumber)+'">#</A></SUP>')
                        outfile.write(' (')
                        if len(item.javadoc.params) > 0:
                            ph = ''
                            for par in item.javadoc.params:
                                ph += ', '+par.sqltype+' '+par.name
                            outfile.write(ph[2:])
                        outfile.write(')</DIV></TD><TD>'+idesc+'</TD></TR>\n')
                        packagedetails += item.javadoc.getHtml(item.uniqueNumber)
            outfile.write('</TABLE>\n\n')

        outfile.write(viewdetails)
        outfile.write(packagedetails)
        # ===[ JAVADOC END ]===

        # include the source itself
        if metaInfo.includeSource:
            outfile.write('\n<H2>Source</H2>\n')
            outfile.write('<code><pre>')
            outfile.write( hypercode(infile_line_list, sqlkeywords, sqltypes) )
            outfile.write("</pre></code>")
            outfile.write(MakeHTMLFooter(file_info.fileName[len(top_level_directory)+1:]))

        outfile.close()

    # print carriage return after last dot
    print


def CreateIndexPage(meta_info):
    """Generates the main index page"""

    html_dir = meta_info.htmlDir
    script_name = meta_info.scriptName

    outfile = open(html_dir + 'index.html', "w")
    outfile.write(MakeHTMLHeader(meta_info, 'Index'))

    # Copy the StyleSheet
    if os.path.exists(meta_info.css_file):
      copy2(meta_info.css_file,html_dir + os.path.split(meta_info.css_file)[1])

    outfile.write("<H1 STYLE='margin-top:100px'>" + metaInfo.title_prefix + " HyperSQL Reference</H1>\n")

    outfile.write("<BR><BR>\n")
    outfile.write("<TABLE ID='projectinfo' ALIGN='center'><TR><TD VALIGN='middle' ALIGN='center'>\n")
    if meta_info.projectLogo != '':
      logoname = os.path.split(meta_info.projectLogo)[1]
      copy2(meta_info.projectLogo,html_dir + logoname)
      outfile.write("  <IMG ALIGN='center' SRC='" + logoname + "' ALT='Logo'><BR><BR><BR>\n")
    outfile.write(meta_info.projectInfo)
    outfile.write("</TD></TR></TABLE>\n")
    outfile.write("<BR><BR>\n")

    outfile.write(MakeHTMLFooter('Index'))
    outfile.close()


def CreateWhereUsedPages(meta_info):
    """Generate a where-used-page for each object"""

    html_dir = meta_info.htmlDir
    fileInfoList = meta_info.fileInfoList

    # loop through files
    dot_count = 1
    for file_info in fileInfoList:

        # skip all non-sql files
        if file_info.fileType != "sql":
            continue

	# print a . every file
	sys.stdout.write(".")
	sys.stdout.flush()
	if (dot_count % 60) == 0: # carriage return every 60 dots
	    print
	    sys.stdout.flush()
	dot_count += 1
	
        # loop through views
        for view_info in file_info.viewInfoList:

            if len(view_info.whereUsed.keys()) == 0:
                continue
            
            #open a "where used" file
            whereusedfilename = "where_used_" + `view_info.uniqueNumber` + ".html"
            outfile = open(html_dir + whereusedfilename, "w")
            
            # write our header
            outfile.write(MakeHTMLHeader(meta_info, 'Index'))
            outfile.write("<H1>" + view_info.viewName + " Where Used List</H1>\n")
            outfile.write("<TABLE CLASS='apilist' ALIGN='center'>\n")
            outfile.write("  <TR><TH>File</TH><TH>Line</TH></TR>\n")

            # each where used
            where_used_keys = view_info.whereUsed.keys()
            where_used_keys.sort(CaseInsensitiveComparison)
            for key in where_used_keys:
                for whereusedtuple in view_info.whereUsed[key]:
                    line_number = whereusedtuple[1]
                    unique_number = whereusedtuple[0].uniqueNumber
                    outfile.write("  <TR><TD>")

                    # only make hypertext references for SQL files for now
                    if whereusedtuple[0].fileType == "sql" and metaInfo.includeSource:
                        outfile.write(key[len(top_level_directory)+1:] + "</TD><TD>")
                        outfile.write("<A href=\"" + os.path.split(key)[1].replace(".", "_"))
                        outfile.write("_" + `unique_number` + ".html" + "#" + `line_number` + "\">")
                        outfile.write( `line_number` + "</A>")
                    else:
                        outfile.write(key[len(top_level_directory)+1:] + "</TD><TD>" + `line_number`)
                    outfile.write("</TD></TR>\n")

            # footer and close
            outfile.write("</TABLE>")
            outfile.write(MakeHTMLFooter(view_info.viewName + " Where Used List"))
            outfile.close()

        for package_info in file_info.packageInfoList:

            if len(package_info.whereUsed.keys()) == 0:
                continue
            
            #open a "where used" file
            whereusedfilename = "where_used_" + `package_info.uniqueNumber` + ".html"
            outfile = open(html_dir + whereusedfilename, "w")
            
            # write our header
            outfile.write(MakeHTMLHeader(meta_info, package_info.packageName + " Where Used List"))
            outfile.write("<H1>" + package_info.packageName + " Where Used List</H1>\n")
            outfile.write("<TABLE CLASS='apilist' ALIGN='center'>\n")
            outfile.write("  <TR><TH>File</TH><TH>Line</TH></TR>\n")

            # each where used
            where_used_keys = package_info.whereUsed.keys()
            where_used_keys.sort(CaseInsensitiveComparison)
            for key in where_used_keys:
                for whereusedtuple in package_info.whereUsed[key]:
                    line_number = whereusedtuple[1]
                    unique_number = whereusedtuple[0].uniqueNumber
                    outfile.write("  <TR><TD>")

                    # only make hypertext references for SQL files for now
                    if whereusedtuple[0].fileType == "sql" and metaInfo.includeSource:
                        outfile.write(key[len(top_level_directory)+1:] + "</TD><TD>")
                        outfile.write("<A href=\"" + os.path.split(key)[1].replace(".", "_"))
                        outfile.write("_" + `unique_number` + ".html" + "#" + `line_number` + "\">")
                        outfile.write(`line_number` + "</A>")
                    else:
                        outfile.write(key[len(top_level_directory)+1:] + "</TD><TD>" + `line_number`)
                    outfile.write("</TD></TR>\n")

            # footer and close
            outfile.write("</TABLE>")
            outfile.write(MakeHTMLFooter(package_info.packageName + " Where Used List"))
            outfile.close()

            #look for any of this packages' functions
            for function_info in package_info.functionInfoList:
                if len(function_info.whereUsed.keys()) == 0:
                    continue
                
                #open a "where used" file
                whereusedfilename = "where_used_" + `function_info.uniqueNumber` + ".html"
                outfile = open(html_dir + whereusedfilename, "w")
                
                # write our header
                outfile.write(MakeHTMLHeader(meta_info, function_info.functionName.lower() + ' from ' + package_info.packageName))
                outfile.write("<H1>" + function_info.functionName.lower() + " <I>from " + package_info.packageName)
                outfile.write(" </I>Where Used List</H1>\n")
                outfile.write("<TABLE CLASS='apilist' ALIGN='center'>\n")
                outfile.write("  <TR><TH>File</TH><TH>Line</TH></TR>\n")

                # each where used
                where_used_keys = function_info.whereUsed.keys()
                where_used_keys.sort(CaseInsensitiveComparison)
                for key in where_used_keys:
                    for whereusedtuple in function_info.whereUsed[key]:
                        line_number = whereusedtuple[1]
                        unique_number = whereusedtuple[0].uniqueNumber

                    # only make hypertext references for SQL files for now
                    outfile.write("  <TR><TD>")
                    if whereusedtuple[0].fileType == "sql" and metaInfo.includeSource:
                        outfile.write(key[len(top_level_directory)+1:] + "</TD><TD>")
                        outfile.write("<A href=\"" + os.path.split(key)[1].replace(".", "_"))
                        outfile.write("_" + `unique_number` + ".html" + "#" + `line_number` + "\">")
                        outfile.write(`line_number` + "</A>")
                    else:
                        outfile.write(key[len(top_level_directory)+1:] + "</TD><TD>" + `line_number`)
                    outfile.write("</TD></TR>\n")

                # footer and close
                outfile.write("</TABLE>")
                outfile.write(MakeHTMLFooter(function_info.functionName.lower() + ' from ' + package_info.packageName))
                outfile.close()

            #look for any of this packages procedures
            for procedure_info in package_info.procedureInfoList:
                if len(procedure_info.whereUsed.keys()) == 0:
                    continue
                
                #open a "where used" file
                whereusedfilename = "where_used_" + `procedure_info.uniqueNumber` + ".html"
                outfile = open(html_dir + whereusedfilename, "w")
                
                # write our header
                outfile.write(MakeHTMLHeader(meta_info, procedure_info.procedureName.lower() + ' from ' + package_info.packageName.lower()))
                outfile.write("<H1>" + procedure_info.procedureName.lower() + " <I>from " + package_info.packageName.lower())
                outfile.write(" </I>Where Used List</H1>\n")
                outfile.write("<TABLE CLASS='apilist' ALIGN='center'>\n")
                outfile.write("  <TR><TH>File</TH><TH>Line</TH></TR>\n")
                
                # each where used
                where_used_keys = procedure_info.whereUsed.keys()
                where_used_keys.sort(CaseInsensitiveComparison)
                for key in where_used_keys:
                    for whereusedtuple in procedure_info.whereUsed[key]:
                        line_number = whereusedtuple[1]
                        unique_number = whereusedtuple[0].uniqueNumber
                        outfile.write("  <TR><TD>")

                        # only make hypertext references for SQL files for now
                        if whereusedtuple[0].fileType == "sql" and metaInfo.includeSource:
                            outfile.write(key[len(top_level_directory)+1:] + "</TD><TD>")
                            outfile.write("<A href=\"" + os.path.split(key)[1].replace(".", "_"))
                            outfile.write("_" + `unique_number` + ".html" + "#" + `line_number` + "\">")
                            outfile.write(`line_number` + "</A>")
                        else:
                            outfile.write(key[len(top_level_directory)+1:] + "</TD><TD>" + `line_number`)
                    outfile.write("</TD></TR>\n")

                # footer and close
                outfile.write("</TABLE>")
                outfile.write(MakeHTMLFooter(procedure_info.procedureName.lower() + ' from ' + package_info.packageName.lower()))
                outfile.close()

    # print carriage return after last dot
    print


def confName(projName):
    """ Get the name of the .ini file to use for configuration """
    if os.path.exists(projName+'.ini'):
      return projName+'.ini'
    if os.path.exists(projName.lower()+'.ini'):
      return projName.lower()+'.ini'
    if os.path.exists('HyperSQL.ini'):
      return 'HyperSQL.ini'
    if os.path.exists('hypersql.ini'):
      return 'hypersql.ini'
    return ''

def confGet(sect,opt,default=''):
    """
    Get an option from the config as string
    Parameters: section name, option name, default value
    """
    if config.has_option(sect,opt):
      return config.get(sect,opt)
    else:
      return default

def confGetList(sect,opt,default=[]):
    """
    Get an option from the config as list
    Parameters: section name, option name, default value
    """
    if config.has_option(sect,opt):
      return config.get(sect,opt).split(' ')
    else:
      return default

def confGetBool(sect,opt,default=False):
    """
    Get an option from the config as boolean value
    Parameters: section name, option name, default value
    """
    if config.has_option(sect,opt):
      return config.getboolean(sect,opt)
    else:
      return default

def confGetInt(sect,opt,default=0):
    """
    Get an option from the config as integer value
    Parameters: section name, option name, default value
    """
    if config.has_option(sect,opt):
      return config.getint(sect,opt)
    else:
      return default

def confPage(page,filenameDefault,pagenameDefault,enableDefault):
    """
    Add the specified page to the list of pages to process if it is enabled
    """
    if confGetBool('Pages',page,enableDefault):
        metaInfo.indexPage[page] = confGet('FileNames',page,filenameDefault)
        metaInfo.indexPageName[page] = confGet('PageNames',page,pagenameDefault)
        metaInfo.indexPageCount += 1
    else:
        metaInfo.indexPage[page] = ''

def configRead():
    # Section GENERAL
    metaInfo.title_prefix  = confGet('General','title_prefix','HyperSQL')
    metaInfo.projectInfo   = confGet('General','project_info','')
    infofile               = confGet('General','project_logo_url','')
    if infofile == '':
      metaInfo.projectLogo = confGet('General','project_logo','')
    else:
      metaInfo.projectLogo = infofile
    infofile               = confGet('General','project_info_file','')
    if infofile != '' and os.path.exists(infofile):
        infile = open(infofile, "r")
        fileLines = infile.readlines()
        infile.close()
        for i in range(len(fileLines)):
            metaInfo.projectInfo += fileLines[i]
    # Section FILENAMES
    metaInfo.topLevelDirectory  = confGet('FileNames','top_level_directory','.') # directory under which all files will be scanned
    metaInfo.rcsnames           = confGetList('FileNames','rcsnames',['RCS','CVS','.svn']) # directories to ignore
    metaInfo.sql_file_exts      = confGetList('FileNames','sql_file_exts',['sql', 'pkg', 'pkb', 'pks', 'pls']) # Extensions for files to treat as SQL
    metaInfo.cpp_file_exts      = confGetList('FileNames','cpp_file_exts',['c', 'cpp', 'h']) # Extensions for files to treat as C
    metaInfo.htmlDir            = confGet('FileNames','htmlDir',os.path.split(sys.argv[0])[0] + os.sep + "html" + os.sep)
    metaInfo.css_file           = confGet('FileNames','css_file','hypersql.css')
    metaInfo.css_url            = confGet('FileNames','css_url','')
    metaInfo.indexPage          = {}
    metaInfo.indexPageCount     = 1 # We at least have the main index page
    metaInfo.indexPageName      = {}
    confPage('filepath','FileNameIndexWithPathnames.html','File Names by Path Index',True)
    confPage('file','FileNameIndexNoPathnames.html','File Name Index',True)
    confPage('view','ViewIndex.html','View Index',False)
    confPage('package','PackageIndex.html','Package Index',True)
    confPage('package_full','PackagesWithFuncsAndProcsIndex.html','Full Package Listing',True)
    confPage('function','FunctionIndex.html','Function Index',True)
    confPage('procedure','ProcedureIndex.html','Procedure Index',True)
    #confPage('bug','BugIndex.html','Bug List',True)
    #confPage('todo','TodoIndex.html','Todo List',True)
    # Sections PAGES and PAGENAMES are handled indirectly via confPage() in section FileNames
    # Section PROCESS
    purgeOnStart = confGetBool('Process','purge_on_start',False)
    metaInfo.blindOffset = abs(confGetInt('Process','blind_offset',0)) # we need a positive integer
    metaInfo.includeSource = confGetBool('Process','include_source',True)


if __name__ == "__main__":

    # Read the config file
    if len(sys.argv)>1:
      configFile = confName(sys.argv[1])
    else:
      configFile = confName('HyperSQL')
    config = ConfigParser.ConfigParser()
    if configFile != '':
      print 'Reading config file ' + configFile
      config.read(configFile)

    metaInfo = MetaInfo() # This holds top-level meta information, i.e., lists of filenames, etc.
    purgeOnStart = False
    configRead()
    top_level_directory = metaInfo.topLevelDirectory
    if not os.path.exists(top_level_directory):
        print "\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n" \
            + "The source path you configured for top_level_directory\n(" \
            + top_level_directory \
            + ")\ndoes not exist - terminating.\n" \
            + "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n"
        sys.exit(os.EX_OSFILE)

    metaInfo.scriptName = sys.argv[0]
    metaInfo.versionString = "1.7"
    metaInfo.toDoList = """
    # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    #   TO-DO LIST
    #
    # A) where used does not work for local functions or procedures
    # B) block comments are not ignored (/* comment block */)
    # C) C++ files need doxygen hyperlinks for where used pages
    # D) Scan Java files for where used
    #
    # If you have an idea for improving hyperSQL, let me know - Randy
    #
    # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    """



    print "Creating file list" 
    FindFilesAndBuildFileList(metaInfo.topLevelDirectory, metaInfo.fileInfoList, metaInfo)

    print "Scanning source files for views and packages"
    ScanFilesForViewsAndPackages(metaInfo)

    print "Scanning source files for where views and packages are used"
    ScanFilesForWhereViewsAndPackagesAreUsed(metaInfo)

    if purgeOnStart and os.path.exists(metaInfo.htmlDir):
      print "Removing html files from previous run"
      names=os.listdir(metaInfo.htmlDir)
      for i in names:
        os.unlink(metaInfo.htmlDir + i)

    print "Creating html subdirectory"
    CreateHTMLDirectory(metaInfo)

    # Generating the index pages
    MakeFileIndexWithPathNames(metaInfo)
    MakeFileIndexNoPathNames(metaInfo)
    MakeViewIndex(metaInfo)
    MakePackageIndex(metaInfo)
    MakeFunctionIndex(metaInfo)
    MakeProcedureIndex(metaInfo)
    MakePackagesWithFuncsAndProcsIndex(metaInfo)

    print "Creating 'where used' pages"
    CreateWhereUsedPages(metaInfo)

    print "Creating hyperlinked source file pages"
    CreateHyperlinkedSourceFilePages(metaInfo)

    print "Creating site index page"
    CreateIndexPage(metaInfo)

    print metaInfo.toDoList

    print "done"
