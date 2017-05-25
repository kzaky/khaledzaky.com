$(function(){
// Homepage | section.blog | article nav behavior
  
  // first, hide everything except 2017 posts be default
  $(".article-item:not(.article-2017)").removeClass("show");

  // if click on All, show all posts
  $("#articlesAllTrigger").on("click", function(event){
    event.preventDefault();
    $(".article-nav .year").removeClass("showing");
    $(this).addClass("showing");
    $(".article-item").addClass("show");
  });

  // if click on 2017, show 2017 posts
  $("#articles2017Trigger").on("click", function(event){
    event.preventDefault();
    $(".article-nav .year").removeClass("showing");
    $(this).addClass("showing");
    $(".article-item").removeClass("show");
    $(".article-item.article-2017").addClass("show");
  });

  // if click on 2016, show 2016 posts
  $("#articles2016Trigger").on("click", function(event){
    event.preventDefault();
    $(".article-nav .year").removeClass("showing");
    $(this).addClass("showing");
    $(".article-item").removeClass("show");
    $(".article-item.article-2016").addClass("show");
  });
});
