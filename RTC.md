# RTC (Relative Time Cost) — relative to subtraction
  
- **RTC** values are **relative to `subtract`** (so `subtract` = 1.0).
- **N/A** means the block is not meant to run as fast as possible for obvious reasons
- 5000.0 values are not actually 5000.0, but means the block causes the script to pause for exactly one frame (causes a screen refresh), so it was given this arbitrary large value.
- For formulas like `a + b·n`, **`n` is the input size** shown in the image (typically list length / string length, depending on the block).

---

## Motion

| block | RTC |
|---|---:|
| movesteps | 7.1 |
| turnright | 6.6 |
| turnleft | 6.6 |
| goto | 7.4 |
| gotoxy | 7.6 |
| glideto | N/A |
| glidesecstoxy | N/A |
| pointindirection | 6.5 |
| pointtowards | 8.1 |
| changexby | 7.4 |
| setx | 7.0 |
| changeyby | 7.4 |
| sety | 7.0 |
| ifonedgebounce | 5.5 |
| setrotationstyle | 6.7 |
| xposition | 0.3 |
| yposition | 0.3 |
| direction | 0.3 |

---

## Looks

| block | RTC |
|---|---:|
| sayforsecs | N/A |
| say | 35.8 |
| thinkforsecs | N/A |
| think | 39.5 |
| switchcostumeto | 304.9 |
| nextcostume | 312.0 |
| switchbackdropto | 14.6 |
| switchbackdroptoandwait | N/A |
| nextbackdrop | 20.1 |
| changesizeby | 23.8 |
| setsizeto | 13.2 |
| changeeffectby:color | 17.4 |
| seteffectto:color | 17.4 |
| changeeffectby:fisheye | 349.0 |
| seteffectto:fisheye | 349.0 |
| changeeffectby:whirl | 336.2 |
| seteffectto:whirl | 336.2 |
| changeeffectby:pixelate | 165.6 |
| seteffectto:pixelate | 165.6 |
| changeeffectby:mosaic | 187.2 |
| seteffectto:mosaic | 187.2 |
| changeeffectby:brightness | 12.8 |
| seteffectto:brightness | 12.8 |
| changeeffectby:ghost | 7.1 |
| seteffectto:ghost | 7.1 |
| cleargraphiceffects | 318.1 |
| show | 27.8 |
| hide | 7.0 |
| gotofrontback | 8.2 |
| goforwardbackwardlayers | 5.6 |
| costumenumbername | 0.1 |
| backdropnumbername | 0.1 |
| size | 0.1 |

---

## Sound

| block | RTC |
|---|---:|
| playuntildone | N/A |
| play | 79.3 |
| stopallsounds | 27.7 |
| changeeffectby | 5000.0 |
| seteffectto | 5000.0 |
| cleareffects | 5.0 |
| changevolumeby | 5000.0 |
| setvolumeto | 5000.0 |
| volume | 0.1 |

---

## Events

| block | RTC |
|---|---:|
| whenflagclicked | 4.0 |
| whenkeypressed | 4.0 |
| whenthisspriteclicked | 4.0 |
| whenstageclicked | 4.0 |
| whenbackdropswitchesto | 4.0 |
| whengreaterthan | 4.0 |
| whenbroadcastreceived | 4.0 |
| broadcast | 15.9 |
| broadcastandwait | N/A |

---

## Control

| block | RTC |
|---|---:|
| wait | N/A |
| repeat | 6.3 |
| forever | 6.3 |
| if | 1.8 |
| ifelse | 4.9 |
| waituntil | 2.6 |
| repeatuntil | 2.8 |
| foreach | 7.7 |
| stop | N/A |
| start as clone | 4.0 |
| create clone of | 79.0 |
| delete this clone | 2.0 |

---

## Sensing

| block | RTC |
|---|---:|
| touchingobject:mouse-pointer | 17.4 |
| touchingobject:edge | 11.8 |
| touchingobject:sprite | 11.8 |
| touchingcolor | 10422.7 |
| coloristouchingcolor | 5993.5 |
| distanceto:mouse-pointer | 2.0 |
| distanceto:sprite | 2.9 |
| askandwait | N/A |
| answer | N/A |
| keypressed | 0.8 |
| mousedown | 0.5 |
| mousex | 0.7 |
| mousey | 0.7 |
| setdragmode | 2.9 |
| loudness | 0.6 |
| timer | 0.6 |
| resettimer | 3.0 |
| of | 0.4 |
| current | 5.1 |
| dayssince2000 | 11.4 |
| username | 1.1 |

---

## Operators

| block | RTC |
|---|---:|
| add | 1.0 |
| subtract | 1.0 |
| multiply | 1.0 |
| divide | 1.0 |
| random | 1.3 |
| gt | 1.0 |
| lt | 1.0 |
| equals | 1.0 |
| and | 0.5 |
| or | 0.5 |
| not | 0.4 |
| join | 0.7 |
| letter of | 0.6 |
| length | 0.5 |
| contains | 1.1 + 0.0038n |
| mod | 1.4 |
| round | 0.5 |
| mathop:abs | 0.8 |
| mathop:floor | 0.7 |
| mathop:ceiling | 0.8 |
| mathop:sqrt | 0.8 |
| mathop:sin | 2.5 |
| mathop:cos | 2.8 |
| mathop:tan | 2.9 |
| mathop:asin | 0.8 |
| mathop:acos | 0.9 |
| mathop:atan | 1.1 |
| mathop:ln | 1.2 |
| mathop:log | 1.0 |
| mathop:e^ | 1.1 |
| mathop:10^ | 1.1 |

---

## Variables

| block | RTC |
|---|---:|
| variable | 0.6 |
| setvariableto | 3.4 |
| changevariableby | 3.5 |
| showvariable | 10.1 |
| hidevariable | 6.7 |

---

## Lists

| block | RTC |
|---|---:|
| listcontents | 3.3 + 0.0945n |
| addtolist | 4.6 |
| deleteoflist | 4.2 |
| deletealloflist | 3.4 |
| insertatlist | 6.4 + 0.0107n |
| replaceitemoflist | 3.7 |
| itemoflist | 2.8 |
| itemnumoflist | 2.8 + 1n |
| lengthoflist | 2.0 |
| listcontainsitem | 2.8 + 1.09n |
| showlist | 7.1 |
| hidelist | 6.7 |

---

## Custom / My Blocks

| block | RTC |
|---|---:|
| definition | 7.7 |
| call | 1.1 + 0.271n |
| reporter string number | 0.6 |
| reporter boolean | 0.6 |

---

## Pen

| block | RTC |
|---|---:|
| clear | 6.6 |
| stamp:vector | 53.9 |
| stamp:bitmap | 46.2 |
| penDown | 18.1 |
| penUp | 3.5 |
| setPenColorToColor | 12.9 |
| changePenColorParamBy | 4.5 |
| setPenColorParamTo | 4.5 |
| changePenSizeBy | 3.5 |
| setPenSizeTo | 3.4 |