<?php
ob_start();

if ($handle = opendir('allletters')) {
    while (false !== ($file = readdir($handle))) {
	
	$contents = file_get_contents("allletters/$file");
      $body = split("<body>", $contents);

	echo ("|");
	echo $file;
	echo ("@");
	echo $body[1];
    }
    closedir($handle);
}
$page = ob_get_contents();
ob_end_flush();
$fp = fopen("all-letter-bodies.txt","w");
fwrite($fp,$page);
fclose($fp);
?>
