

// Some archive actions should be executed before this script run.
// This script will copy the changelog.xml from each build archive directory to build root directory.
// e.g. from: <JENKINS_HOME>/jobs/<JOB_NAME>/builds/<BUILD_NUMBER>/archive) to :<JENKINS_HOME>/jobs/<JOB_NAME>/builds/<BUILD_NUMBER>
import hudson.model.*;
import java.lang.ref.WeakReference;
import hudson.plugins.accurev.*;

def buildRootDir = "${manager.getEnvVariable("JENKINS_HOME")}/jobs/${manager.getEnvVariable("JOB_NAME")}/builds/${manager.getEnvVariable("BUILD_NUMBER")}"
def changeLogFileName = "changelog.xml"
def changeLogFile = "${buildRootDir}/${changeLogFileName}"

// Do the copy
new File("${changeLogFile}").text = new File("${buildRootDir}/archive/${changeLogFileName}").text

// Fake an AccurevSCM, please ignore the parameters in the constructor.
def accurevSCM = new AccurevSCM("serverName","depot","stream","wspaceORreftree","workspace","reftree","subPath","filterForPollSCM",true,true,true,"snapshotNameFormat","directoryOffset",true)
def parser = accurevSCM.createChangeLogParser()

def build = manager.build
def changeLogSet = parser.parse(build, new java.io.File(changeLogFile))

def buildSCMField = build.getClass().getSuperclass().getSuperclass().getDeclaredField("scm")
buildSCMField.setAccessible(true)
buildSCMField.set(build, parser)

def changeSetField = build.getClass().getSuperclass().getSuperclass().getDeclaredField("changeSet")
changeSetField.setAccessible(true)
changeLogSet = new WeakReference<hudson.scm.ChangeLogSet<? extends hudson.scm.ChangeLogSet.Entry>>(changeLogSet)
changeSetField.set(build, changeLogSet)




import hudson.model.*
import hudson.AbortException
import hudson.console.HyperlinkNote
import java.util.concurrent.CancellationException
##build=hudson.model.FreeStyleBuild
println('--------------Start groovy sciprt-------------')
println('This is:'+build.getClass())
def foo = build.buildVariableResolver.resolve("bc-d1010")
println "FOO=$foo"
##job=hudson.model.FreeStyleProject
def job = Hudson.instance.getJob('Install image on bc or bs')
def anotherBuild
try {
    def params = [
      new StringParameterValue('swarmName', 'bc-d1010'),
    ]
    def future = job.scheduleBuild2(0, new Cause.UpstreamCause(build), new ParametersAction(params))
    println "Waiting for the completion of " + HyperlinkNote.encodeTo('/' + job.url, job.fullDisplayName)
    anotherBuild = future.get()
} catch (CancellationException x) {
    throw new AbortException("${job.fullDisplayName} aborted.")
}

// Check that it succeeded
build.result = anotherBuild.result
if (anotherBuild.result != Result.SUCCESS && anotherBuild.result != Result.UNSTABLE) {
    // We abort this build right here and now.
    throw new AbortException("${anotherBuild.fullDisplayName} failed.")
}

// Do something with the output.
// On the contrary to Parameterized Trigger Plugin, you may now do something from that other build instance.
// Like the parsing the build log (see http://javadoc.jenkins-ci.org/hudson/model/FreeStyleBuild.html )
// You probably may also wish to update the current job's environment.
build.addAction(new ParametersAction(new StringParameterValue('BAR', '3')))







####
import jenkins.model.Jenkins
println(Jenkins.instance.getAllItems())
println(Jenkins.instance.getJobNames())
println(Jenkins.instance.getNodes())
println(Jenkins.instance.getLabels())
Jenkins.instance.getItems()
Jenkins.instance.getItem('upc-longa4-private1-usr_Build-test').getName()
Jenkins.instance.getItem('upc-longa4-private1-usr_Build-test')

import hudson.model.Build
Jenkins.instance.()
Jenkins.instance.()
Jenkins.instance.()
Jenkins.instance.()
Jenkins.instance.()
Jenkins.instance.()
Jenkins.instance.()
Jenkins.instance.()
Jenkins.instance.()
Jenkins.instance.()













import hudson.model.*
import java.util.Date
import groovy.json.JsonBuilder

accurevStream = params["ACCUREV_STREAM"]
suseSlave = false
winSlave = false
rhSlave = false

buildStartBuild = null
buildCS = null
buildImage = null
buildVNX2 = null
suseMutTest = null
winMutTest = null
testWorkflow = null
emailInfoFile = new File("jobs/${build.project.name}/builds/${build.number}/email-info.log")

runBuild()
report()

def runBuild() {
  accurevInit()
  checkSlaves()
  parallelBuilds()
}

def report() {
  //Log children jobs information into a file, email template will use the file to generate the report
  childJobLog = new JsonBuilder()
  parallelJobs = []
  if(buildCS != null) {
    parallelJobs.push ({
      jobName  buildCS.project.name
      buildUrl    buildCS.url
      jobResult buildCS.result.toString()
      buildNumber buildCS.number
      buildLog buildCS.log
    })
  }

  if(buildImage != null) {
    parallelJobs.push({
      jobName  buildImage.project.name
      buildUrl    buildImage.url
      jobResult buildImage.result.toString()
      buildNumber buildImage.number
      buildLog buildImage.log
    })
  }

  if(suseMutTest != null) {
    parallelJobs.push({
      jobName  suseMutTest.project.name
      buildUrl    suseMutTest.url
      jobResult suseMutTest.result.toString()
      buildNumber suseMutTest.number
      buildLog suseMutTest.log
    })
  }


  if(buildVNX2 != null) {
    parallelJobs.push({
      jobName  buildVNX2.project.name
      buildUrl    buildVNX2.url
      jobResult buildVNX2.result.toString()
      buildNumber buildVNX2.number
      buildLog buildVNX2.log
    })
  }


  if(winMutTest != null) {
    parallelJobs.push({
      jobName  winMutTest.project.name
      buildUrl    winMutTest.url
      jobResult winMutTest.result.toString()
      buildNumber winMutTest.number
      buildLog winMutTest.log
    })
  }

  childJobLog.parallels {
  jobs parallelJobs
}

childJobLog.children {
  parallelJobs parallelJobs
  startbuild {
    jobName  buildStartBuild.project.name
    buildUrl    buildStartBuild.url
    jobResult buildStartBuild.result.toString()
    buildNumber buildStartBuild.number
    buildLog buildStartBuild.log
  }  
}

emailInfoFile << childJobLog.toPrettyString()
}

//Start build, accurev init
def accurevInit() {
  println ""
  print new Date()
  println "  Starting Accurev transaction checking..."
  buildStartBuild = build("upc-RmtFSMigration-Stream-jobs/upc-RmtFSMigration-cs_Start-Build", 
    ACCUREV_STREAM: accurevStream)

  transactionId = buildStartBuild.environment.get( "ACCUREV_LAST_TRANSACTION" )
}

//Check if the needed slaves are existed
def checkSlaves() {
  for (aSlave in Hudson.instance.slaves) {
    def label = aSlave.getLabelString()
    if (label.indexOf("SUSE-BUILD") != -1) {    
      suseSlave = true    
    }
    if(label.indexOf("WIN-BUILD") != -1) {
      winSlave = true    
    }
    if(label.indexOf("RH-BUILD") != -1) {
      rhSlave = true    
    }
  }
  println ""
  print new Date()
  println "  Checking Slaves..."
  if(!suseSlave) {println "No SUSE machine, cannot build image."}
  if(!winSlave) {println "No Windows machine, cannot build VNX2 safe"}
  if(!rhSlave) {println "No RedHat Machine, cannot build controlStation"}
  println "Done"
}

def parallelBuilds() {
  //construct parallel jobs list
  def parallelBuildJobs = []
    //build ControlStation
  if(params["BUILD_REDHAT"] == "true" && rhSlave == true) {
    parallelBuildJobs.push({buildCS = build("upc-longa4-private1-usr_Build-Redhat", TRANSACTION_ID: transactionId, ACCUREV_STREAM: accurevStream)})
  }
    //build Image
  if(params["BUILD_SUSE"] == "true" && suseSlave == true) {
    parallelBuildJobs.push({buildImage = build("upc-longa4-private1-usr_Build-Suse", TRANSACTION_ID: transactionId, ACCUREV_STREAM: accurevStream)})
  }
      //build VNX2 safe
  if(params["BUILD_WINDOWS"] == "true" && winSlave == true) {
    parallelBuildJobs.push({
      buildVNX2 = build("upc-longa4-private1-usr_Build-Windows", TRANSACTION_ID: transactionId, ACCUREV_STREAM: accurevStream)
    })
  }
      //Parallel build the jobs
  println ""
  print new Date()  // timestamp
  println "  Starting Parallel Jobs..." 
  parallel(parallelBuildJobs)
}

//Debug environment variables
//buildStartBuild.build.environment.each { out.println "$it.key -> $it.value" }
  
  
  
  
  
  
  
  
  
  
  
  
  
  
  
  
  
import hudson.model.*
import hudson.AbortException
import hudson.console.HyperlinkNote
import java.util.concurrent.CancellationException
//build=hudson.model.FreeStyleBuild
println('--------------Start groovy sciprt-------------')
println('This is:'+build.getClass())
def foo = build.buildVariableResolver.resolve("bc-d1010")
println "FOO=$foo"
//job=hudson.model.FreeStyleProject
def job = Hudson.instance.getJob('Install image on bc or bs')
def anotherBuild
try {
    def params = [
      new StringParameterValue('swarmName','bc-d1010'),
    ]
    def future = job.scheduleBuild2(0, new Cause.UpstreamCause(build), new ParametersAction(params))
    println "Waiting for the completion of " + HyperlinkNote.encodeTo('/' + job.url, job.fullDisplayName)
    anotherBuild = future.get()
} catch (CancellationException x) {
    throw new AbortException("${job.fullDisplayName} aborted.")
}  