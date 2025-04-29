import { Component } from '@angular/core';

@Component({
  selector: 'app-footer',
  imports: [],
  template: `<!--begin::To the end-->
  <div class="float-end d-none d-sm-inline">Anything you want</div>
  <!--end::To the end-->
  <!--begin::Copyright-->
  <strong>
    Copyright &copy; 2015 - 2025&nbsp;
    <a href="https://buddhilive.com" class="text-decoration-none">Buddhilive</a
    >.
  </strong>
  All rights reserved.
  <!--end::Copyright-->`,
})
export class FooterComponent {

}
