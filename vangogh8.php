<?php
ob_start();

// Doctype and styles
// ------------------------------

echo ('

<kml xmlns="http://www.opengis.net/kml/2.2"
 xmlns:gx="http://www.google.com/kml/ext/2.2">


  <Document>
    <name>Van Gogh Letters - 8</name>

 <Style id="city">


<IconStyle>      
<Icon><href>http://jamesmuspratt.com/vangogh/city.png</href></Icon>
  <scale>.25</scale>
</IconStyle>      
 </Style>

 <Style id="vincent">


<IconStyle>      
<Icon><href>http://jamesmuspratt.com/vangogh/vincent.png</href></Icon>
  <scale>.25</scale>
</IconStyle>      
 </Style>

<Style id="theo">


<IconStyle> 
<Icon><href>http://jamesmuspratt.com/vangogh/theo.png</href></Icon>     
  <scale>.25</scale>
</IconStyle>          
</Style>


 <Style id="line">

    <LineStyle>
     <color>ffffffff</color>
  <colorMode>normal</colorMode>   
 <width>1</width>
    </LineStyle>
  </Style>
');


// Poor man's database
// ------------------------------

$longitude['Antwerp'] = 4.417;
$latitude['Antwerp'] = 51.217;

$longitude['Brussels'] = 4.353;
$latitude['Brussels'] = 50.847;

$longitude['Cuesmes'] =3.917;
$latitude['Cuesmes'] = 50.433;

$longitude['Laeken'] = 4.35;	
$latitude['Laeken'] = 50.867;

$longitude['Petit-Wasmes'] = 3.817;	
$latitude['Petit-Wasmes'] = 50.417;

$longitude['Arles'] = 4.63;	
$latitude['Arles'] = 43.677;

$longitude['Auvers-sur-Oise'] = 2.167;
$latitude['Auvers-sur-Oise'] = 49.067;

$longitude['Paris'] = 2.33;	
$latitude['Paris'] = 48.867;

$longitude['Saint-Remy'] = 4.832;	
$latitude['Saint-Remy'] = 43.788;

$longitude['Amsterdam'] = 	4.9;
$latitude['Amsterdam'] = 52.373;

$longitude['Dordrecht'] = 4.674;	
$latitude['Dordrecht'] = 51.81;

$longitude['Drenthe'] = 6.583;	
$latitude['Drenthe'] = 52.833;

$longitude['Etten'] = 6.336;
$latitude['Etten'] = 51.917;

$longitude['Helvoirt'] = 5.231;	
$latitude['Helvoirt'] = 51.632;

$longitude['Nuenen'] = 5.553;	
$latitude['Nuenen'] = 51.47;

$longitude['The Hague']	 = 4.299;	
$latitude['The Hague'] = 52.077;

$longitude['Oisterwijk'] = 5.198;	
$latitude['Oisterwijk'] = 51.581;

$longitude['Isleworth'] = -0.333;	
$latitude['Isleworth'] = 51.467;

$longitude['London'] = -0.126;
$latitude['London'] = 51.508;

$longitude['Ramsgate'] = 1.433;	
$latitude['Ramsgate'] = 51.333;

// Plot the cities

$cities =  array_keys($longitude);

echo ("  <Folder>
	<name>Cities</name>");

foreach ($cities as $key) {

echo ("	

	<Placemark>
		<name>$key</name>
  <styleUrl>#city</styleUrl>
		<Point>
	        <altitudeMode>relativeToGround</altitudeMode>
<coordinates>$longitude[$key], $latitude[$key], 0</coordinates>
		</Point>
	</Placemark>
	");
	}
echo ("</Folder>");






// DOT LOOP
// ------------------------------


echo ("
<Folder>
<name>Dots</name>
				");
// Starting altitude and width (for line only)
$thisaltitude=0;
$thiswidth = 1;


//Import CSV file and start LOOP 

  $fh = fopen("vangogh.csv", "r");
   while (list($filename, $date, $from, $to, $contents) = 
	fgetcsv($fh, 1024, ",")) {

// Date stuff
list($displayyear, $displaymonth, $displayday) = split('[/.-]', $date); 
$displaymonth =  date('F', mktime(0, 0, 0, $displaymonth)); 
$displaydate = "$displaymonth $displayday, $displayyear";


// Assign coordinates for this point/line
$thisfromlong = $longitude[$from];
$thisfromlat =  $latitude[$from];
$thistolong = $longitude[$to];
$thistolat = $latitude[$to];

// Test if we're already on this line. 
// If so, elevate.
if  (
	($prevfromlong == $thisfromlong AND
	$prevfromlat == $thisfromlat AND
	$prevtolong == $thistolong AND
	$prevtolat == $thistolat))
	 	{
		$thisaltitude = $thisaltitude + 500;
		}
	else {
		$thisaltitude=0;
		}
	
echo ("
<ScreenOverlay>
<TimeStamp>
<when>$date</when>
</TimeStamp>
<name>$letter</name>
<Icon>
<href>http://jamesmuspratt.com/vangogh/dot.png</href>
</Icon>
<overlayXY x=\"1\" y=\"-1\" xunits=\"fraction\" yunits=\"fraction\"/>
<screenXY x=\"1\" y=\"0\" xunits=\"fraction\" yunits=\"fraction\"/>
<size x=\"0\" y=\"0\" xunits=\"fraction\" yunits=\"fraction\"/>
</ScreenOverlay>
");

	$prevfromlong = $thisfromlong;
	$prevfromlat = $thisfromlat;
	$prevtolong = $thistolong;
	$prevtolat = $thistolat;
}

echo ("
</Folder>
				");



// Starting altitude and width (for line only)
$thisaltitude=0;
$thiswidth = 1;


echo ("  <Folder>
	<name>Locations and Lines</name>");


//Import CSV file and start LOOP 

  $fh = fopen("vangogh.csv", "r");
   while (list($filename, $date, $from, $to, $contents) = 
	fgetcsv($fh, 1024, ",")) {

// Date stuff
list($displayyear, $displaymonth, $displayday) = split('[/.-]', $date); 
$displaymonth =  date('F', mktime(0, 0, 0, $displaymonth)); 
$displaydate = "$displaymonth $displayday, $displayyear";


// Assign coordinates for this point/line
$thisfromlong = $longitude[$from];
$thisfromlat =  $latitude[$from];
$thistolong = $longitude[$to];
$thistolat = $latitude[$to];

// Test if we're already on this line. 
// If so, elevate.
if  (
	($prevfromlong == $thisfromlong AND
	$prevfromlat == $thisfromlat AND
	$prevtolong == $thistolong AND
	$prevtolat == $thistolat))
	 	{
		$thisaltitude = $thisaltitude + 500;
		}
	else {
		$thisaltitude=0;
		}
	

echo ("
	<Placemark>
		<name>$displaydate</name>
  <styleUrl>#vincent</styleUrl>
		<TimeStamp>
		<when>$date</when>
		</TimeStamp>
		<description><![CDATA[
				<style>		
		body {width:500px; font-family:georgia, serif;font-size:11px;line-height:16px;}
		body h2 {font-family:georgia, serif;font-weight:normal;font-size:9px;letter-spacing:1px;text-transform:uppercase;}
		</style>
		<body>
		<h2>Letter $filename</h2>
		$contents
		</body>
		]]>
		</description>
		<Point>
	        <altitudeMode>relativeToGround</altitudeMode>
	<coordinates>$thisfromlong,$thisfromlat,$thisaltitude</coordinates>
		</Point>
	</Placemark>
	
	<Placemark>
	<name>$filename line</name>
    <styleUrl>#line</styleUrl>
  		<TimeStamp>
		<when>$date</when>
	</TimeStamp>
		<Style>
		<LineStyle>
		<width>$thiswidth</width> 
		</LineStyle>
		</Style>
		<LineString>
		<extrude>0</extrude>
		<tessellate>1</tessellate>
        <altitudeMode>clampToGround</altitudeMode>
 <coordinates>$thisfromlong,$thisfromlat,$thisaltitude $thistolong,$thistolat,$thisaltitude</coordinates>
    </LineString>
	</Placemark>



");

	$prevfromlong = $thisfromlong;
	$prevfromlat = $thisfromlat;
	$prevtolong = $thistolong;
	$prevtolat = $thistolat;
}

echo ("
	</Folder>
	</Document>
	</kml>
");

$page = ob_get_contents();
ob_end_flush();
$fp = fopen("vangogh8.kml","w");
fwrite($fp,$page);
fclose($fp);
?>
