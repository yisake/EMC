Binding binding = getBinding();
binding.rooturl = jenkins.model.Jenkins.getInstance().getRootUrl()

// Compatibility logic for the Groovy Postbuild Plugin
if (binding.getVariables().keySet().contains("manager")) {
  binding.build = manager.build
}

class Result {
  def testName
  def totalSubtests
  def passedSubtests
  def failedSubtests
  def testDuration
  def passed
  def textExecutable
}

class Change {
  def date
  def author
  def AR
  def msg
  def filesChanged = []
}

binding.parseLog = { logname ->
  def tests = []

  try {
    def logfile = new hudson.FilePath(build.getWorkspace(), logname)
    def reader = new java.io.BufferedReader(new java.io.InputStreamReader(logfile.read()))

    def it = "" // Unhelpful variable name because this was a closure previously
    while ((it = reader.readLine()) != null) {
      def r = new Result()
      def tokens = it.split(" ");

      r.testName = tokens[0];
      r.totalSubtests = tokens[1]
      r.passedSubtests = tokens[2]
      r.failedSubtests = tokens[3]
      r.testDuration = tokens[4]

      if (r.testName.equals("TOTALS:")) {
        r.testName = "<b>" + tokens[0] + "</b>"
        r.totalSubtests = "<b>" + tokens[1] + "</b>"
        r.passedSubtests = "<b>" + tokens[2] + "</b>"
        r.failedSubtests = "<b>" + tokens[3] + "</b>"
        r.testDuration = "<b>" + tokens[4] + "</b>"
        r.passed = ""
        r.textExecutable = ""
      } else {
        r.passed = tokens[5].equals("PASSED")
        r.textExecutable = tokens[6]
      }

      tests.add(r)
    }

    // logfile.delete()
  } catch (java.io.FileNotFoundException e) {}

  return tests
}

binding.getChangeset = {
 def changeSet = build.changeSet
  changes = []

  if (changeSet != null && !changeSet.isEmptySet()) {
    def df = new java.text.SimpleDateFormat("yyyy-MM-dd hh:mm:ss")

    changeSet.each {
      if (!"promote".equals(it.action)) {
        return
      }

      def change = new Change()
      change.author = it.author
      change.msg = it.msg.replaceAll('\n', "<br/>")
      change.date = df.format(it.date)

      it.affectedPaths.each {
        def info = it.split("<br/>.*Issue Number - ")

        file = info[0]
        if (info.length > 1) {
          change.AR = info[1]
        } else {
          file = file.split("<br/>.*")[0]
          change.AR = '?'
        }

        change.filesChanged.add(file)
      }
      change.filesChanged.sort()
      changes.add(change)
    }

    changes.sort { it.date }
  }
  
  return changes
}

binding.appendHead = { stringBuilder ->
  stringBuilder.append("""\
<head>
<!-- Needed to prevent Outlook from showing "If there are problems with how this message is displayed, click here to view it in a web browser" -->
<meta name="ProgId" content="Word.Document">""")

  appendStyleBlock(stringBuilder)

  stringBuilder.append("""\
</head>
<body>""")
}

binding.appendStyleBlock = { stringBuilder ->
  stringBuilder.append("""
<style>
.normal {
  font-family:Verdana,Helvetica,sans-serif;
  font-size:11px;
  color:black;
}
.section-header {
  font-family:Verdana,Helvetica,sans-serif;
  font-size:13.5px;
  font-weight:bold;
  text-align:center;
  vertical-align:middle;
}
.results {
  background:gainsboro;
  font-size:12pt;
  font-family:Arial,sans-serif;
  text-align:center;
  vertical-align:middle;
}
.results-header {
  font-size:13.5pt;
  font-family:Arial,sans-serif;
  font-weight:bold;
  text-align:center;
  vertical-align:middle;
}
</style>""")
}

binding.appendSummaryBlock = { stringBuilder ->
  stringBuilder.append("""
<!-- HEADER -->
<TABLE>
  <TR><TD style="text-align:right"><IMG SRC="${rooturl}static/e59dfe28/images/32x32/${build.result.color}.gif"/></TD>
      <TD style="vertical-align:middle"><B class=normal style="font-size: 17pt;">BUILD ${build.result}</B></TD></TR>
  <TR><TD class=normal>Build URL</TD><TD><A class=normal style="color:blue;" href="${rooturl}${build.url}">${java.net.URLDecoder.decode(rooturl+build.url, "UTF-8")}</A></TD></TR>
  <TR><TD class=normal>Project:</TD><TD class=normal>${build.getProject().name}</TD></TR>""")
  if (build.environment.containsKey("accurev_workspace") && !build.environment.accurev_workspace.isEmpty()) {
    stringBuilder.append("""
  <TR><TD class=normal>Workspace:</TD><TD class=normal>${build.environment.accurev_workspace}</TD></TR>""")
  }
  if (build.environment.containsKey("stream")) {
    stringBuilder.append("""
  <TR><TD class=normal>Stream:</TD><TD class=normal>${build.environment.stream}</TD></TR>""")
  }
  
  stringBuilder.append("""
  <TR><TD class=normal>Platform:</TD><TD class=normal>${build.getBuiltOn().toComputer().isUnix() ? "Linux" : "Windows"}</TD></TR>
  <TR><TD class=normal>Date of build:</TD><TD class=normal>${build.getTimestamp().getTime().toString()}</TD></TR>
  <TR><TD class=normal>Build duration:</TD><TD class=normal>${build.durationString}</TD></TR>
</TABLE>
<!-- END HEADER -->""")
}

binding.appendTestSuite = { stringBuilder ->
  // If the list is empty the file didn't exist, so skip printing the table
  if (!tests.isEmpty()) {
    stringBuilder.append("""
<!-- TEST STATUS -->
<br/>
<table border="1">
  <caption>
    <h3 class=normal style="font-size:13.5pt;text-align:center;vertical-align:middle;">Suite Summary</h3>
  </caption>
  <thead>
    <tr>
      <td class=results-header>Suite Name</td>
      <td class=results-header>Total</td>
      <td class=results-header>Passed</td>
      <td class=results-header>Failed</td>
      <td class=results-header>Duration</td>
      <td class=results-header>Result</td>
      <td class=results-header>Executable Name</td>
    </tr>
  </thead>
  <tbody>""")
    tests.each {
      stringBuilder.append("""
    <tr>
      <td class=results>${it.testName}</td>
      <td class=results>${it.totalSubtests}</td>
      <td class=results>${it.passedSubtests}</td>
      <td class=results>${it.failedSubtests}</td>
      <td class=results>${it.testDuration}</td>
      <td class=results style="background-color:${(it.passed == true) ? "lightgreen\">Passed" : (it.passed == false) ? "red\">Failed" : "gainsboro\">" + it.passed}</td>
      <td class=results>${it.textExecutable}</td>
    </tr>""")
    }
    stringBuilder.append("""
  </tbody>
</table>
<!-- END TEST STATUS -->""")
  
    // If the size is zero, the file didn't exist
    // If the size is one, it's just the "summary" line with no tests
    // Either way, we don't want to include the table
    if (secondary.size() > 1) {
      stringBuilder.append("""
<!-- STANDALONE TEST STATUS -->
<br/>
<table border="1">
  <caption>
    <h3 class=section-header>Standalone Test Summary</h3>
  </caption>
  <thead>
    <tr>
      <td class=results-header>Suite Name</td>
      <td class=results-header>Total</td>
      <td class=results-header>Passed</td>
      <td class=results-header>Failed</td>
      <td class=results-header>Duration</td>
      <td class=results-header>Result</td>
      <td class=results-header>Executable Name</td>
    </tr>
  </thead>
  <tbody>""")
      secondary.each {
        stringBuilder.append("""
    <tr>
      <td class=results>${it.testName}</td>
      <td class=results>${it.totalSubtests}</td>
      <td class=results>${it.passedSubtests}</td>
      <td class=results>${it.failedSubtests}</td>
      <td class=results>${it.testDuration}</td>
      <td class=results style="background-color:${(it.passed == true) ? "lightgreen\">Passed" : (it.passed == false) ? "red\">Failed" : "gainsboro\">" + it.passed}</td>
      <td class=results>${it.textExecutable}</td>
    </tr>""")
      }
      stringBuilder.append("""
  </tbody>
</table>
<!-- END STANDALONE TEST STATUS -->""")
    }
  }
}

binding.tests = parseLog("suite.log")
binding.secondary = parseLog("standalone.log")
binding.changes = getChangeset()
